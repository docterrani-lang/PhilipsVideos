import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
from email.message import EmailMessage

# --- CONFIGURAZIONE (Dati fissi) ---
ADMIN_USER = "Admin"
ADMIN_PASS = "Philips!"
# Carichiamo la lista dai secrets
AUTHORIZED_EMAILS = st.secrets["AUTHORIZED_EMAILS"]

# Connessione R2
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
        st.error(f"Errore mail: {e}")
        return False

# --- GESTIONE STATO LOGIN ---
if "login_step" not in st.session_state:
    st.session_state.login_step = "start" # start, verify_otp, authorized

# --- INTERFACCIA LOGIN ---

if st.session_state.login_step == "start":
    st.title("🔐 Login Portale")
    identificativo = st.text_input("Inserisci Username o Email")
    password_admin = st.text_input("Password (solo se sei Admin)", type="password")

    if st.button("Procedi"):
        # 1. È l'Admin?
        if identificativo == ADMIN_USER and password_admin == ADMIN_PASS:
            st.session_state.role = "admin"
            st.session_state.login_step = "authorized"
            st.rerun()
        
        # 2. È un utente autorizzato?
        elif identificativo in AUTHORIZED_EMAILS:
            otp = str(random.randint(100000, 999999))
            st.session_state.generated_otp = otp
            st.session_state.target_email = identificativo
            
            with st.spinner("Invio codice in corso..."):
                if send_otp(identificativo, otp):
                    st.session_state.login_step = "verify_otp"
                    st.rerun()
        else:
            st.error("Accesso non autorizzato per questo identificativo.")

elif st.session_state.login_step == "verify_otp":
    st.title("📧 Verifica Codice")
    st.write(f"Abbiamo inviato un codice a: **{st.session_state.target_email}**")
    codice_inserito = st.text_input("Inserisci il codice ricevuto via mail")
    
    col1, col2 = st.columns(2)
    if col1.button("Verifica e Entra"):
        if codice_inserito == st.session_state.generated_otp:
            st.session_state.role = "user"
            st.session_state.login_step = "authorized"
            st.rerun()
        else:
            st.error("Codice non corretto.")
            
    if col2.button("Torna indietro"):
        st.session_state.login_step = "start"
        st.rerun()

# --- AREA RISERVATA (Una volta loggati) ---
if st.session_state.login_step == "authorized":
    st.sidebar.title("Opzioni")
    if st.sidebar.button("Logout"):
        st.session_state.login_step = "start"
        st.rerun()

    if st.session_state.role == "admin":
        st.header("🛠️ Dashboard Amministratore")
        # Inserisci qui il codice per caricare/cancellare video (già fatto sopra)
    else:
        st.header("📺 I tuoi Video")
        # Inserisci qui il codice per la selectbox e il player video
