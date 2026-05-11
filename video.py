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

# --- CSS DEFINITIVO (FORZATO) ---
st.markdown("""
    <style>
    /* 1. SFONDO GENERALE E TESTI BASE */
    .stApp { background-color: #0066a1 !important; }
    
    /* Forza il colore bianco su TUTTE le scritte standard */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp div {
        color: #ffffff !important;
        font-family: 'Calibri', sans-serif;
    }

    /* 2. PULSANTI: Sfondo Bianco, Testo BLU PHILIPS */
    /* Questo selettore è molto specifico per catturare il testo dentro il bottone */
    button[kind="primary"], button[kind="secondary"], .stButton > button {
        background-color: #ffffff !important;
        border: none !important;
        height: 45px !important;
        width: 100% !important;
        border-radius: 4px !important;
    }
    
    /* Forza il colore del testo del pulsante in Blu */
    .stButton > button p, .stButton > button div, .stButton > button span {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* 3. NOME UTENTE IN GIALLO (Pagina Verifica) */
    .user-yellow {
        color: #ffff00 !important;
        font-size: 22px !important;
        font-weight: bold !important;
        display: block;
        margin-bottom: 10px;
    }

    /* 4. TESTI EVIDENZIATI (Box Riproduzione) */
    .highlight-box {
        background-color: rgba(255, 255, 255, 0.2);
        color: #ffffff !important;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #ffff00;
        margin-bottom: 20px;
    }
    
    /* 5. INPUT FIELDS (Scritta Blu dentro fondo Bianco) */
    input {
        color: #0066a1 !important;
    }

    /* Fix per messaggi Error/Info */
    .stAlert p {
        color: #000000 !important; /* Testo nero su box colorati per leggibilità */
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI (REINSERITE PER SICUREZZA) ---
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

# --- LOGICA DI ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"
if "show_feedback" not in st.session_state: st.session_state.show_feedback = False

if st.session_state.login_step in ["step1", "step2"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("## 🏥 Spectral CT Portal")
        
        if st.session_state.login_step == "step1":
            uid = st.text_input("Username o Email")
            if st.button("PROSEGUI"):
                if uid == "Admin": # Sostituire con ADMIN_USER se variabile presente
                    st.session_state.temp_user = uid
                    st.session_state.login_step = "step2"
                    st.rerun()
                elif uid in st.secrets.get("AUTHORIZED_EMAILS", []):
                    otp = str(random.randint(100000, 999999))
                    st.session_state.generated_otp = otp
                    st.session_state.temp_user = uid
                    if send_otp(uid, otp):
                        st.session_state.login_step = "step2"
                        st.rerun()
        
        elif st.session_state.login_step == "step2":
            # APPLICAZIONE CLASSE GIALLA
            st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == "Admin" else "default")
            if st.button("CONFERMA"):
                if secret == st.session_state.get("generated_otp") or secret == "Philips!":
                    st.session_state.login_step = "authorized"
                    st.rerun()
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.markdown("# 📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    col_v, col_l = st.columns([3, 1])
    
    with col_l:
        st.markdown("### Webinar Library")
        # Esempio pulsante video
        if st.button("▶ Webinar Introduzione"):
            st.session_state.active_video = "Webinar Introduzione"
        
        st.divider()
        if st.button("🚪 LOGOUT"):
            st.session_state.login_step = "step1"
            st.rerun()

    with col_v:
        if "active_video" in st.session_state:
            st.markdown(f"<div class='highlight-box'>Stai guardando: {st.session_state.active_video}</div>", unsafe_allow_html=True)
            st.info("Video in caricamento...")
        else:
            st.write("Seleziona un webinar dalla lista a destra.")
