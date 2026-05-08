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

# --- FUNZIONE INVIO MAIL ---
def send_otp(target_email, code):
    msg = EmailMessage()
    msg.set_content(f"Il tuo codice di accesso per il portale video è: {code}")
    msg["Subject"] = "Codice di Verifica"
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = target_email
    try:
        # Usiamo STARTTLS per massima compatibilità con Gmail
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Errore tecnico invio mail: {e}")
        return False

# --- GESTIONE STATO ---
if "login_step" not in st.session_state:
    st.session_state.login_step = "step1" # step1, step2, authorized

# --- STEP 1: IDENTIFICAZIONE ---
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
            with st.spinner("Invio codice OTP in corso..."):
                if send_otp(user_id, otp):
                    st.session_state.login_step = "step2"
                    st.rerun()
        else:
            st.error("Utente non autorizzato.")

# --- STEP 2: VERIFICA (PASSWORD O OTP) ---
elif st.session_state.login_step == "step2":
    st.title("🛡️ Verifica Identità")
    
    if st.session_state.temp_user == ADMIN_USER:
        st.write("Identità confermata: **Amministratore**")
        secret = st.text_input("Inserisci Password Admin", type="password")
    else:
        st.write(f"Codice inviato a: **{st.session_state.temp_user}**")
        secret = st.text_input("Inserisci il codice OTP ricevuto via mail")

    col1, col2 = st.columns(2)
    if col1.button("Accedi"):
        # Verifica Admin
        if st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS:
            st.session_state.role = "admin"
            st.session_state.login_step = "authorized"
            st.rerun()
        # Verifica Utente
        elif secret == st.session_state.generated_otp:
            st.session_state.role = "user"
            st.session_state.login_step = "authorized"
            st.rerun()
        else:
            st.error("Credenziali o codice non validi.")

    if col2.button("Annulla / Cambia Utente"):
        st.session_state.login_step = "step1"
        st.rerun()

# --- AREA RISERVATA ---
if st.session_state.login_step == "authorized":
    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({"login_step": "step1"}))
    
    # ... qui inserisci la logica dei video (list_videos, st.video, ecc.) ...
    st.success(f"Benvenuto nel portale ({st.session_state.role})")
