import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
import json
from email.message import EmailMessage
from datetime import datetime
import io

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- CSS RADICALE (Risolve i bottoni bianchi vuoti) ---
st.markdown("""
    <style>
    /* Sfondo e Font */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* Testi base bianchi */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small {
        color: #ffffff !important;
    }

    /* FIX BOTTONI: Forza il testo blu su QUALSIASI elemento interno */
    /* Questo corregge le aree cerchiate in rosso nei tuoi screenshot */
    button, div.stButton > button, div.stFormSubmitButton > button, 
    div.stDownloadButton > button, [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px !important;
    }

    /* Selettore universale per il contenuto dei bottoni */
    button *, div.stButton > button *, [data-testid="stFileUploadDropzone"] button * {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
    }

    /* Username e Feedback */
    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .feedback-card { 
        background-color: rgba(255, 255, 255, 0.15); 
        padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #ffff00; 
    }
    
    /* Input scuri per leggibilità */
    input, textarea { color: #004d7a !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI CORE ---
# Carichiamo i segreti (Assicurati che siano su Streamlit Cloud)
try:
    s3 = boto3.client("s3", 
        endpoint_url=st.secrets["R2_ENDPOINT"],
        aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
        aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )
    BUCKET = st.secrets["BUCKET_NAME"]
except Exception as e:
    st.error(f"Errore configurazione S3: {e}")

def load_json(f):
    try:
        res = s3.get_object(Bucket=BUCKET, Key=f)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(f, d): 
    s3.put_object(Bucket=BUCKET, Key=f, Body=json.dumps(d))

# --- GESTIONE NAVIGAZIONE ---
if "login_step" not in st.session_state: 
    st.session_state.login_step = "step1"

# STEP 1: SCHERMATA LOGIN (Se vedi blu, il problema è qui)
if st.session_state.login_step == "step1":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        st.title("Accesso Portale")
        uid = st.text_input("Username o Email")
        if st.button("PROSEGUI"):
            if uid: # Semplificato per test, poi aggiungi i tuoi controlli
                st.session_state.temp_user = uid
                st.session_state.login_step = "step2"
                st.rerun()

# STEP 2: VERIFICA
elif st.session_state.login_step == "step2":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.title("Verifica")
        st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
        pwd = st.text_input("Codice o Password", type="password")
        if st.button("CONFERMA"):
            st.session_state.role = "admin" if st.session_state.temp_user.lower() == "admin" else "user"
            st.session_state.login_step = "authorized"
            st.rerun()

# AREA AUTORIZZATA
elif st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    if st.session_state.role == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("#### 📩 Richieste Accesso")
            reqs = load_json("richieste_accesso.json")
            for r in reqs: st.text(f"• {r.get('email', 'N/A')}")
            if st.button("Svuota Richieste"):
                save_json("richieste_accesso.json", [])
                st.rerun()
                
        with c2:
            st.markdown("#### 💬 Feedback")
            fbs = load_json("feedback_webinar.json")
            for f in reversed(fbs[-3:]): # Mostra ultimi 3
                st.markdown(f"""<div class="feedback-card">
                    <b style="color:#ffff00">{f['valutazione']}</b><br>
                    <small>{f['user']}</small><br>
                    {f.get('richieste', '')}
                </div>""", unsafe_allow_html=True)
            if st.button("Svuota Feedback"):
                save_json("feedback_webinar.json", [])
                st.rerun()

        with c3:
            st.markdown("#### 📤 Caricamento Video")
            up = st.file_uploader("Seleziona MP4", type=['mp4'])
            if up and st.button("CARICA ORA"):
                s3.upload_fileobj(up, BUCKET, up.name)
                st.success("Video caricato!")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
