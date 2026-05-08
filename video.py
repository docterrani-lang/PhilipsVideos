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

# Connessione R2
s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

# --- FUNZIONE INVIO MAIL ---
def send_otp(target_email, code):
    msg = EmailMessage()
    msg.set_content(f"Il tuo codice di accesso per il portale video è: {code}")
    msg["Subject"] = "Codice di Verifica Portale Video"
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = target_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Errore invio mail: {e}")
        return False

# --- LOGICA DI ACCESSO ---
if "auth_status" not in st.session_state:
    st.session_state.auth_status = "logged_out" # logged_out, otp_sent, authorized

if st.session_state.auth_status == "logged_out":
    st.title("🔐 Login")
    u = st.text_input("Username / Email")
    p = st.text_input("Password (solo per Admin)", type="password")

    if st.button("Accedi / Invia Codice"):
        # CASO ADMIN
        if u == ADMIN_USER and p == ADMIN_PASS:
            st.session_state.auth_status = "authorized"
            st.session_state.role = "admin"
            st.rerun()
        
        # CASO UTENTE (OTP)
        elif u in AUTHORIZED_EMAILS:
            otp_code = str(random.randint(100000, 999999))
            st.session_state.generated_otp = otp_code
            st.session_state.target_email = u
            if send_otp(u, otp_code):
                st.session_state.auth_status = "otp_sent"
                st.rerun()
        else:
            st.error("Email non autorizzata o credenziali errate.")

elif st.session_state.auth_status == "otp_sent":
    st.title("📧 Verifica Email")
    st.info(f"Abbiamo inviato un codice a {st.session_state.target_email}")
    input_otp = st.text_input("Inserisci il codice di 6 cifre")
    
    if st.button("Verifica"):
        if input_otp == st.session_state.generated_otp:
            st.session_state.auth_status = "authorized"
            st.session_state.role = "user"
            st.rerun()
        else:
            st.error("Codice errato.")
    
    if st.button("Annulla"):
        st.session_state.auth_status = "logged_out"
        st.rerun()

# --- APP PRINCIPALE ---
if st.session_state.auth_status == "authorized":
    st.title("🎬 Portale Video")
    
    if st.sidebar.button("Logout"):
        st.session_state.auth_status = "logged_out"
        st.rerun()

    # Qui va il resto del tuo codice per mostrare/caricare i video...
    # (Usa list_videos() e st.video() come negli step precedenti)
