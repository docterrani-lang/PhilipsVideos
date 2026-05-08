import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
from email.message import EmailMessage

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- CSS PERSONALIZZATO (Calibri + Layout) ---
st.markdown("""
    <style>
    /* Forza il carattere Calibri */
    html, body, [class*="st-"] {
        font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif;
    }
    
    /* Nasconde il tasto download nei video */
    video::-internal-media-controls-download-button { display:none; }
    video::-webkit-media-controls-enclosure { overflow:hidden; }
    video::-webkit-media-controls-panel { width: calc(100% + 30px); }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAZIONE CREDENZIALI ---
ADMIN_USER = "Admin"
ADMIN_PASS = "Philips!"
AUTHORIZED_EMAILS = st.secrets["AUTHORIZED_EMAILS"]

# Connessione Cloudflare R2
s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]

# --- FUNZIONI ---
def send_otp(target_email, code):
    msg = EmailMessage()
    msg.set_content(f"Il tuo codice di accesso per il portale PHILIPS SPECTRAL CT WEBINAR è: {code}")
    msg["Subject"] = "Codice di Verifica Philips Webinar"
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = target_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore tecnico invio mail: {e}")
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
    st.subheader("Accesso Riservato")
    user_id = st.text_input("Inserisci Username o Email")
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
            st.error("Utente non autorizzato.")
    st.stop()

elif st.session_state.login_step == "step2":
    st.title("🛡️ Verifica Identità")
    if st.session_state.temp_user == ADMIN_USER:
        secret = st.text_input("Inserisci Password Admin", type="password")
    else:
        st.info(f"Codice inviato a: {st.session_state.temp_user}")
        secret = st.text_input("Inserisci il codice OTP ricevuto")
    
    if st.button("Accedi"):
        if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
            st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
            st.session_state.login_step = "authorized"
            st.rerun()
        else:
            st.error("Credenziali errate.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # Creiamo due colonne: la prima grande per il video (75%), la seconda per la lista (25%)
    col_video, col_lista = st.columns([3, 1])
    
    videos = list_videos()

    with col_lista:
        st.markdown("### 🎞️ Lista Webinar")
        for v in videos:
            # Rimuoviamo l'estensione .mp4 dal nome del bottone per estetica
            display_name = v.replace('.mp4', '')
            if st.button(display_name, key=v, use_container_width=True):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.login_step = "step1"
            st.rerun()

    with col_video:
        if "active_video" in st.session_state:
            st.subheader(f"In riproduzione: {st.session_state.active_video.replace('.mp4', '')}")
            url = get_signed_url(st.session_state.active_video)
            st.video(url)
        else:
            if videos:
                st.info("Seleziona un webinar dalla lista a destra per iniziare la visione.")
            else:
                st.warning("Nessun webinar disponibile al momento.")
        
        # Pannello Admin sotto il video (solo per Admin)
        if st.session_state.role == "admin":
            st.divider()
            with st.expander("🛠️ Area Caricamento Video"):
                up = st.file_uploader("Trascina qui il file MP4", type=['mp4'])
                if up and st.button("Pubblica Webinar"):
                    with st.spinner("Caricamento..."):
                        s3.upload_fileobj(up, BUCKET, up.name)
                        st.success("Webinar caricato correttamente!")
                        st.rerun()
