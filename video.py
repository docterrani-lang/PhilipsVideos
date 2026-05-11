import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
import json
from email.message import EmailMessage
from datetime import datetime
import io

# --- TENTATIVO CARICAMENTO LIBRERIA PDF ---
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- CSS FINALE ULTRA-AGGRESSIVO PER I TASTI ---
st.markdown("""
    <style>
    /* 1. Sfondo e Testi Base */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small { color: #ffffff !important; }

    /* 2. FIX PULSANTI GENERALI */
    div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px;
    }
    div.stButton > button *, div.stFormSubmitButton > button *, div.stDownloadButton > button * {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* 3. FIX DEFINITIVO PER IL TASTO UPLOAD (L'AREA BIANCA) */
    /* Colpisce il contenitore del file uploader */
    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed rgba(255,255,255,0.5) !important;
        background-color: rgba(255,255,255,0.05) !important;
    }

    /* Colpisce specificamente il bottone interno al file uploader */
    [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        color: #0066a1 !important;
        border: none !important;
    }

    /* FORZA IL COLORE DEL TESTO "BROWSE FILES" O "SFOGLIA" */
    /* Usiamo !important su ogni possibile elemento interno */
    [data-testid="stFileUploadDropzone"] button div {
        color: #0066a1 !important;
    }
    
    [data-testid="stFileUploadDropzone"] span {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* Rende visibile il testo informativo accanto al tasto */
    [data-testid="stFileUploadDropzone"] section div div {
        color: #ffffff !important;
    }

    /* 4. Feedback e Altro */
    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
    .admin-box { background-color: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); margin-top: 30px; }
    .feedback-card { background-color: rgba(255, 255, 255, 0.15); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #ffff00; }
    input, textarea { color: #004d7a !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI CORE (CARICAMENTO E SALVATAGGIO) ---
s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]

def load_json(f):
    try:
        res = s3.get_object(Bucket=BUCKET, Key=f)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(f, d): s3.put_object(Bucket=BUCKET, Key=f, Body=json.dumps(d))

# --- LOGICA DI ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"

# [Mantenere qui la parte di Login Step 1 e 2 come nelle versioni precedenti]

if st.session_state.get("login_step") == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    if st.session_state.get("role") == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        with c3:
            st.markdown("#### 📤 Upload Video")
            # Questo widget ora prenderà i colori corretti grazie al CSS sopra
            up = st.file_uploader("Seleziona Video MP4", type=['mp4'], key="admin_uploader")
            if up and st.button("ESEGUI CARICAMENTO"):
                with st.spinner("Caricamento in corso..."):
                    s3.upload_fileobj(up, BUCKET, up.name)
                    st.success("Video caricato correttamente!")
                    st.rerun()
        
        # [Mantenere colonne c1 e c2 per Richieste e Feedback]
        st.markdown('</div>', unsafe_allow_html=True)
