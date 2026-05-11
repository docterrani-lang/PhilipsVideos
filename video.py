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

# --- PHILIPS BRAND DESIGN (CSS) ---
st.markdown("""
    <style>
    /* Sfondo Generale Philips Blue */
    .stApp {
        background-color: #0066a1;
        color: #ffffff;
    }
    
    /* Font Calibri */
    html, body, [class*="st-"] {
        font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif;
    }

    /* Card per i contenuti */
    .stMarkdown, .stButton, .stTextInput, .stFileUploader {
        color: #333333;
    }

    /* Stile per i titoli */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: bold;
    }

    /* Box bianchi per input e pannelli */
    div.stTextInput > div > div > input {
        background-color: #ffffff;
        color: #0066a1;
    }

    /* Pulsanti lista video (Bianchi con testo blu) */
    div.stButton > button {
        background-color: #ffffff;
        color: #0066a1;
        border: 1px solid #ffffff;
        border-radius: 4px;
        font-weight: bold;
        transition: all 0.3s;
        height: 45px;
    }
    
    div.stButton > button:hover {
        background-color: #e6e6e6;
        color: #004d7a;
        border: 1px solid #e6e6e6;
    }

    /* Pulsante Logout / Svuota (Rosso soft o trasparente) */
    .logout-btn button {
        background-color: transparent !important;
        color: #ffcccc !important;
        border: 1px solid #ffcccc !important;
    }

    /* Nascondi download video */
    video::-internal-media-controls-download-button { display:none; }
    
    /* Pannello Admin */
    .admin-box {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
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

# Layout Login centrato
if st.session_state.login_step in ["step1", "step2"]:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=200) # Logo Philips bianco se possibile
        
        if st.session_state.login_step == "step1":
            st.title("Spectral CT Webinar Portal")
            user_id = st.text_input("Username o Email")
            if st.button("ACCEDI"):
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
                st.error("Accesso non autorizzato.")
                if st.button("RICHIEDI REGISTRAZIONE"):
                    save_request(st.session_state.pending_email)
                    st.success("Richiesta inviata.")
                    st.session_state.show_reg_popup = False

        elif st.session_state.login_step == "step2":
            st.title("Verifica Identità")
            st.write(f"Utente: {st.session_state.temp_user}")
            secret = st.text_input("Password o OTP", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("VERIFICA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"
                    st.rerun()
                else: st.error("Codice errato.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.title("PHILIPS SPECTRAL CT WEBINAR")
    
    col_video, col_lista = st.columns([3, 1])
    videos = list_videos()

    with col_lista:
        st.subheader("Webinar Library")
        for v in videos:
            name = v.replace('.mp4', '')
            if st.button(f"▶ {name}", key=v):
                st.session_state.active_video = v
        
        st.divider()
        st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
        if st.button("ESCI"):
            st.session_state.login_step = "step1"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_video:
        if "active_video" in st.session_state:
            st.subheader(f"Video: {st.session_state.active_video.replace('.mp4', '')}")
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("Benvenuto. Seleziona un webinar dalla lista a destra per iniziare.")
        
        # --- SEZIONE ADMIN (Stilizzata) ---
        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙ Pannello Amministratore")
            adm1, adm2 = st.columns(2)
            with adm1:
                st.markdown("**Richieste Pendenti:**")
                reqs = get_requests()
                if reqs:
                    for r in reqs:
                        st.text(f"• {r['email']}")
                    if st.button("Svuota Richieste"):
                        clear_requests()
                        st.rerun()
                else: st.write("Nessuna richiesta.")
            
            with adm2:
                st.markdown("**Carica Nuovo Webinar:**")
                up = st.file_uploader("Scegli MP4", type=['mp4'])
                if up and st.button("Pubblica"):
                    s3.upload_fileobj(up, BUCKET, up.name)
                    st.success("Caricato!")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
