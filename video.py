import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
import json
from email.message import EmailMessage
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- CSS PERSONALIZZATO ---
st.markdown("""
    <style>
    html, body, [class*="st-"] {
        font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif;
    }
    video::-internal-media-controls-download-button { display:none; }
    .stButton button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- CREDENZIALI E CONNESSIONI ---
ADMIN_USER = "Admin"
ADMIN_PASS = "Philips!"
AUTHORIZED_EMAILS = st.secrets.get("AUTHORIZED_EMAILS", [])

s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]
REQ_FILE = "richieste_accesso.json"

# --- FUNZIONI ---
def send_otp(target_email, code):
    msg = EmailMessage()
    msg.set_content(f"Il tuo codice di accesso per PHILIPS SPECTRAL CT WEBINAR è: {code}")
    msg["Subject"] = "Codice di Verifica Philips"
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = target_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except: return False

def get_requests():
    try:
        response = s3.get_object(Bucket=BUCKET, Key=REQ_FILE)
        return json.loads(response['Body'].read().decode('utf-8'))
    except: return []

def save_request(email):
    reqs = get_requests()
    if not any(r['email'] == email for r in reqs):
        reqs.append({"email": email, "date": datetime.now().strftime("%d/%m/%Y %H:%M")})
        s3.put_object(Bucket=BUCKET, Key=REQ_FILE, Body=json.dumps(reqs))
        return True
    return False

def clear_requests():
    s3.put_object(Bucket=BUCKET, Key=REQ_FILE, Body=json.dumps([]))

def list_videos():
    try:
        res = s3.list_objects_v2(Bucket=BUCKET)
        return [obj['Key'] for obj in res.get('Contents', []) if obj['Key'].endswith('.mp4')]
    except: return []

def get_signed_url(key):
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

# --- LOGICA DI ACCESSO ---
if "login_step" not in st.session_state:
    st.session_state.login_step = "step1"
if "show_reg_popup" not in st.session_state:
    st.session_state.show_reg_popup = False

if st.session_state.login_step == "step1":
    st.title("🔐 PHILIPS SPECTRAL CT WEBINAR")
    user_id = st.text_input("Username o Email")
    
    if st.button("Continua"):
        if user_id == ADMIN_USER:
            st.session_state.temp_user = user_id
            st.session_state.login_step = "step2"
            st.rerun()
        elif user_id in AUTHORIZED_EMAILS:
            otp = str(random.randint(100000, 999999))
            st.session_state.generated_otp = otp
            st.session_state.temp_user = user_id
            if send_otp(user_id, otp):
                st.session_state.login_step = "step2"
                st.rerun()
        else:
            st.session_state.pending_email = user_id
            st.session_state.show_reg_popup = True

    if st.session_state.show_reg_popup:
        st.error(f"L'utente {st.session_state.pending_email} non risulta autorizzato.")
        c1, c2 = st.columns(2)
        if c1.button("Richiedi Registrazione"):
            save_request(st.session_state.pending_email)
            st.success("Richiesta inviata all'amministratore.")
            st.session_state.show_reg_popup = False
        if c2.button("Annulla"):
            st.session_state.show_reg_popup = False
            st.rerun()
    st.stop()

elif st.session_state.login_step == "step2":
    st.title("🛡️ Verifica")
    if st.session_state.temp_user == ADMIN_USER:
        secret = st.text_input("Password Amministratore", type="password")
    else:
        st.info(f"Inserisci il codice inviato a {st.session_state.temp_user}")
        secret = st.text_input("Codice OTP")
    
    if st.button("Accedi"):
        if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
            st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
            st.session_state.login_step = "authorized"
            st.rerun()
        else: st.error("Codice o Password errati.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    col_video, col_lista = st.columns([3, 1])
    videos = list_videos()

    with col_lista:
        st.markdown("### 🎞️ Lista Webinar")
        for v in videos:
            name = v.replace('.mp4', '')
            if st.button(f"▶️ {name}", key=v):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("🚪 Esci"):
            st.session_state.login_step = "step1"
            st.rerun()

    with col_video:
        if "active_video" in st.session_state:
            st.subheader(f"In riproduzione: {st.session_state.active_video.replace('.mp4', '')}")
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("Scegli un webinar dalla lista a destra per iniziare.")
        
        # --- SEZIONE GESTIONE (Solo Admin) ---
        if st.session_state.role == "admin":
            st.divider()
            st.subheader("⚙️ Pannello di Controllo")
            
            adm1, adm2 = st.columns(2)
            with adm1:
                st.markdown("**📥 Richieste di Accesso**")
                reqs = get_requests()
                if reqs:
                    for r in reqs:
                        st.text(f"• {r['email']} ({r['date']})")
                    # PULSANTE PER CANCELLARE LA LISTA
                    if st.button("🗑️ Svuota Lista Richieste"):
                        clear_requests()
                        st.success("Lista svuotata!")
                        st.rerun()
                else: 
                    st.write("Nessuna richiesta pendente.")
            
            with adm2:
                st.markdown("**📤 Carica Webinar**")
                up = st.file_uploader("Scegli file MP4", type=['mp4'])
                if up and st.button("Pubblica Ora"):
                    with st.spinner("Caricamento..."):
                        s3.upload_fileobj(up, BUCKET, up.name)
                        st.success("Caricato con successo!")
                        st.rerun()
