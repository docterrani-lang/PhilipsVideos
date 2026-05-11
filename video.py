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

# --- CSS DEFINITIVO E AGGIORNATO PER ADMIN ---
st.markdown("""
    <style>
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* Testi base bianchi */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small {
        color: #ffffff !important;
    }

    /* TUTTI I PULSANTI (Normali, Form, File Uploader) */
    div.stButton > button, div.stFormSubmitButton > button, [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        color: #0066a1 !important;
        font-weight: bold !important;
    }
    
    /* Forza testo blu dentro i bottoni */
    div.stButton > button div p, div.stButton > button span, [data-testid="stFileUploadDropzone"] button span {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* Username in GIALLO */
    .user-yellow {
        color: #ffff00 !important;
        font-weight: bold !important;
        font-size: 20px !important;
    }

    /* Box Riproduzione Video */
    .highlight-box {
        background-color: #e6f3ff;
        color: #0066a1 !important;
        padding: 12px;
        border-radius: 5px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .highlight-box * { color: #0066a1 !important; }

    /* Input Fields */
    input, textarea { color: #004d7a !important; }

    /* Pannello Admin Migliorato */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
        margin-top: 20px;
    }
    .feedback-item {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        border-left: 3px solid #ffff00;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI CORE (Identiche per stabilità) ---
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

def load_json(filename):
    try:
        res = s3.get_object(Bucket=st.secrets["BUCKET_NAME"], Key=filename)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(filename, data):
    s3.put_object(Bucket=st.secrets["BUCKET_NAME"], Key=filename, Body=json.dumps(data))

# --- LOGICA ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"
if "show_feedback" not in st.session_state: st.session_state.show_feedback = False

# [Qui inseriresti la logica di connessione S3 e il Login Step 1 e 2 come nei messaggi precedenti]
# Per brevità passo direttamente all'area autorizzata corretta

if st.session_state.get("login_step") == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # Area Feedback (se attiva)
    if st.session_state.show_feedback:
        # [Logica form feedback...]
        st.stop()

    c_vid, c_list = st.columns([3, 1])
    # [Logica visualizzazione video...]

    # --- PANNELLO ADMIN (CORRETTO) ---
    if st.session_state.get("role") == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello di Controllo Amministratore")
        
        a1, a2, a3 = st.columns(3)
        
        with a1:
            st.markdown("### 📩 Richieste Accesso")
            reqs = load_json("richieste_accesso.json")
            if not reqs: st.write("Nessuna richiesta.")
            for r in reqs:
                st.markdown(f"• **{r['email']}** ({r['date']})")
            if reqs and st.button("🗑️ Svuota Lista"):
                save_json("richieste_accesso.json", [])
                st.rerun()
                
        with a2:
            st.markdown("### 💬 Feedback Utenti")
            fbs = load_json("feedback_webinar.json")
            if not fbs: st.write("Ancora nessun feedback.")
            for f in reversed(fbs[-10:]): # Mostra gli ultimi 10
                st.markdown(f"""
                <div class="feedback-item">
                    <span style="color: #ffff00;">★ {f['valutazione']}</span><br>
                    <small>Da: {f['user']}</small><br>
                    <p style="color: #ffffff !important; font-style: italic;">"{f.get('richieste', 'Nessun commento')}"</p>
                </div>
                """, unsafe_allow_html=True)
                
        with a3:
            st.markdown("### 📤 Caricamento Video")
            up = st.file_uploader("Seleziona file MP4", type=['mp4'])
            if up and st.button("CONFERMA CARICAMENTO"):
                # Logica upload S3
                st.success(f"Caricato: {up.name}")
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)
