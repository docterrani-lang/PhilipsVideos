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

# --- CSS PERSONALIZZATO (Calibri + Layout) ---
st.markdown("""
    <style>
    html, body, [class*="st-"] {
        font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif;
    }
    video::-internal-media-controls-download-button { display:none; }
    .video-item { margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAZIONE ---
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

# --- FUNZIONI SERVIZIO ---
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

    # Popup di Registrazione
    if st.session_state.get("show_reg_popup"):
        st.warning(f"L'utente **{st.session_state.pending_email}** non è registrato.")
        col_reg, col_exit = st.columns(2)
        if col_reg.button("Invia richiesta di registrazione"):
            if save_request(st.session_state.pending_email):
                st.success("Richiesta inviata! L'amministratore ti contatterà presto.")
            else:
                st.info("Hai già inviato una richiesta per questa email.")
            st.session_state.show_reg_popup = False
        if col_exit.button("Esci"):
            st.session_state.show_reg_popup = False
            st.rerun()
    st.stop()

elif st.session_state.login_step == "step2":
    st.title("🛡️ Verifica")
    secret = st.text_input("Codice OTP o Password Admin", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
    if st.button("Accedi"):
        if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
            st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
            st.session_state.login_step = "authorized"
            st.rerun()
        else: st.error("Dati non validi.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    col_video, col_lista = st.columns([3, 1])
    videos = list_videos()

    with col_lista:
        st.markdown("### 🎞️ Elenco Webinar")
        for v in videos:
            display_name = f"🎞️ {v.replace('.mp4', '')}"
            if st.button(display_name, key=v, use_container_width=True):
                st.session_state.active_video = v
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.login_step = "step1"
            st.rerun()

    with col_video:
        if "active_video" in st.session_state:
            st.subheader(f"Video: {st.session_state.active_video.replace('.mp4', '')}")
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("Seleziona un webinar dalla lista a destra.")
        
        # --- SEZIONE ADMIN ---
        if st.session_state.role == "admin":
            st.divider()
            adm_col1, adm_col2 = st.columns(2)
            with adm_col1:
                with st.expander("📥 Richieste di Accesso"):
                    reqs = get_requests()
                    if reqs:
                        for r in reqs:
                            st.write(f"📧 **{r['email']}** - {r['date']}")
                        st.caption("Aggiungi queste mail ai Secrets di Streamlit per abilitarle.")
                    else: st.write("Nessuna richiesta pendente.")
            with adm_col2:
                with st.expander("📤 Carica Video"):
                    up = st.file_uploader("File MP4", type=['mp4'])
                    if up and st.button("Pubblica"):
                        s3.upload_fileobj(up, BUCKET, up.name)
                        st.success("Caricato!")
                        st.rerun()
