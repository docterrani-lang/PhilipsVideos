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

# --- CSS AGGIORNATO (RISOLUTIVO PER TESTI INVISIBILI) ---
st.markdown("""
    <style>
    /* 1. Sfondo e Testi Base */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small { color: #ffffff !important; }

    /* 2. FIX DEFINITIVO PULSANTI (Bianchi con testo Blu) */
    /* Puntiamo a tutti i tipi di bottoni: normali, form, download e uploader */
    div.stButton > button, 
    div.stFormSubmitButton > button, 
    div.stDownloadButton > button, 
    [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px;
        width: 100%;
        transition: 0.3s;
    }

    /* FORZA IL COLORE BLU SU QUALSIASI COSA DENTRO IL BOTTONE */
    /* Questo risolve il problema delle aree rosse negli screenshot */
    div.stButton > button *, 
    div.stFormSubmitButton > button *, 
    div.stDownloadButton > button *,
    [data-testid="stFileUploadDropzone"] button * {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
    }

    /* 3. Username in GIALLO */
    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; display: block; margin-bottom: 10px; }

    /* 4. Pannello Admin e Card */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid rgba(255, 255, 255, 0.3); 
        margin-top: 30px; 
    }
    .feedback-card { 
        background-color: rgba(255, 255, 255, 0.15); 
        padding: 12px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        border-left: 4px solid #ffff00; 
    }
    
    /* Input colorati correttamente */
    input, textarea { color: #004d7a !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI UTILI ---
def generate_pdf(data, title):
    if not PDF_ENABLED: return None
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16); p.drawString(100, 750, title)
    p.setFont("Helvetica", 10); y = 720
    for item in data:
        p.drawString(100, y, f"- {item}"); y -= 20
        if y < 50: p.showPage(); y = 750
    p.save(); buffer.seek(0)
    return buffer

# Connessione S3/R2 (Usa i tuoi secrets esistenti)
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

# STEP 1: LOGIN
if st.session_state.login_step == "step1":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        uid = st.text_input("Username o Email")
        if st.button("PROSEGUI"):
            if uid == "Admin" or uid in st.secrets.get("AUTHORIZED_EMAILS", []):
                st.session_state.temp_user = uid
                st.session_state.login_step = "step2"; st.rerun()

# STEP 2: VERIFICA
if st.session_state.login_step == "step2":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
        pwd = st.text_input("Codice o Password", type="password")
        if st.button("CONFERMA"):
            st.session_state.role = "admin" if st.session_state.temp_user == "Admin" else "user"
            st.session_state.login_step = "authorized"; st.rerun()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # Sezione Admin
    if st.session_state.role == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("#### 📩 Richieste")
            reqs = load_json("richieste_accesso.json")
            for r in reqs: st.text(f"• {r['email']}")
            if reqs and PDF_ENABLED:
                st.download_button("Scarica PDF Richieste", generate_pdf([r['email'] for r in reqs], "Richieste Accesso"), "richieste.pdf")
            if st.button("Svuota Lista Richieste"): 
                save_json("richieste_accesso.json", []); st.rerun()
            
        with c2:
            st.markdown("#### 💬 Feedback")
            fbs = load_json("feedback_webinar.json")
            for f in reversed(fbs[-3:]):
                st.markdown(f'<div class="feedback-card"><b style="color:#ffff00">{f["valutazione"]}</b><br>{f.get("richieste","")}</div>', unsafe_allow_html=True)
            if fbs and PDF_ENABLED:
                st.download_button("Scarica PDF Feedback", generate_pdf([f["valutazione"] for f in fbs], "Feedback Webinar"), "feedback.pdf")
            if st.button("Svuota Tutti i Feedback"): 
                save_json("feedback_webinar.json", []); st.rerun()

        with c3:
            st.markdown("#### 📤 Upload")
            up = st.file_uploader("Seleziona Video MP4", type=['mp4'])
            if up and st.button("ESEGUI CARICAMENTO"): 
                s3.upload_fileobj(up, BUCKET, up.name); st.success("Video caricato!"); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
