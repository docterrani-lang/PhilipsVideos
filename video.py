import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
from email.message import EmailMessage

# --- CONFIGURAZIONE ---
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

# --- FUNZIONI DI SERVIZIO ---
def send_otp(target_email, code):
    msg = EmailMessage()
    msg.set_content(f"Il tuo codice di accesso per il portale video è: {code}")
    msg["Subject"] = "Codice di Verifica"
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
    except Exception as e:
        st.error(f"Errore nel recupero lista video: {e}")
        return []

def get_signed_url(key):
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

# --- GESTIONE STATO ---
if "login_step" not in st.session_state:
    st.session_state.login_step = "step1"

# --- FLUSSO DI LOGIN ---
if st.session_state.login_step == "step1":
    st.title("🔐 Accesso Portale")
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

# --- AREA RISERVATA (LOGGATO) ---
if st.session_state.login_step == "authorized":
    
    # --- SIDEBAR (Lista Video e Logout) ---
    with st.sidebar:
        st.title("📺 Libreria Video")
        st.write(f"Connesso come: **{st.session_state.role.upper()}**")
        
        videos = list_videos()
        
        st.subheader("Seleziona un video:")
        video_scelto = None
        for v in videos:
            if st.button(v, use_container_width=True):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("🚪 Logout"):
            st.session_state.login_step = "step1"
            st.rerun()

    # --- CONTENUTO CENTRALE ---
    st.title("🎬 Video Player")
    
    # Se l'admin vuole caricare file
    if st.session_state.role == "admin":
        with st.expander("🛠️ Pannello Gestione (Solo Admin)"):
            up = st.file_uploader("Carica nuovo MP4", type=['mp4'])
            if up and st.button("Inizia Upload"):
                s3.upload_fileobj(up, BUCKET, up.name)
                st.success("Caricato!")
                st.rerun()

    # Visualizzazione Video
    if "active_video" in st.session_state:
        st.subheader(f"In riproduzione: {st.session_state.active_video}")
        url = get_signed_url(st.session_state.active_video)
        
        # CSS per bloccare il tasto download
        st.markdown("""
            <style> video::-internal-media-controls-download-button { display:none; } </style>
            """, unsafe_allow_html=True)
        
        st.video(url)
    else:
        if videos:
            st.info("👈 Seleziona un video dalla lista a sinistra per iniziare la visione.")
        else:
            st.warning("Nessun video trovato nel database.")
