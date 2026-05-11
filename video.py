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

# --- CSS (FIX ICONE E PULSANTI ADMIN) ---
st.markdown("""
    <style>
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small { color: #ffffff !important; }

    /* Fix Pulsanti: elimina icone strane e forza colore blu */
    div.stButton > button, div.stFormSubmitButton > button, [data-testid="stFileUploadDropzone"] button, .stDownloadButton > button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px;
        width: 100%;
        color: #0066a1 !important;
    }
    
    /* Pulizia scritte interne ai bottoni */
    div.stButton > button div p, div.stButton > button span, .stDownloadButton > button span {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
        display: inline-block !important;
    }

    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
    .highlight-box { background-color: #e6f3ff; color: #0066a1 !important; padding: 15px; border-radius: 5px; border-left: 6px solid #ffff00; margin-bottom: 20px; }
    .admin-box { background-color: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); margin-top: 30px; }
    .feedback-card { background-color: rgba(255, 255, 255, 0.15); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #ffff00; }
    </style>
    """, unsafe_allow_html=True)

# --- TENTATIVO CARICAMENTO LIBRERIA PDF ---
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# --- FUNZIONE PDF ---
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

# --- CONNESSIONE R2 ---
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

# --- LOGICA LOGIN ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"

# NOTA: Qui dovresti avere il tuo codice di Login (Step 1 e 2).
# Se l'app è blu è perché st.session_state.login_step non cambia.
# Assicurati di inserire i blocchi di input (Username/Email) qui sotto.

if st.session_state.login_step == "step1":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        uid = st.text_input("Username o Email")
        if st.button("PROSEGUI"):
            if uid == "Admin" or uid in st.secrets.get("AUTHORIZED_EMAILS", []):
                st.session_state.temp_user = uid
                st.session_state.login_step = "step2"; st.rerun()

if st.session_state.login_step == "step2":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
        pwd = st.text_input("Codice o Password", type="password")
        if st.button("CONFERMA"):
            st.session_state.role = "admin" if st.session_state.temp_user == "Admin" else "user"
            st.session_state.login_step = "authorized"; st.rerun()

# --- PORTALE ---
if st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # Area Admin
    if st.session_state.role == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.write("**Richieste:**")
            reqs = load_json("richieste_accesso.json")
            for r in reqs: st.text(f"• {r['email']}")
            if reqs and PDF_ENABLED:
                st.download_button("Scarica PDF Richieste", generate_pdf([r['email'] for r in reqs], "Richieste"), "richieste.pdf")
            if st.button("Svuota Richieste"): save_json("richieste_accesso.json", []); st.rerun()
            
        with c2:
            st.write("**Feedback:**")
            fbs = load_json("feedback_webinar.json")
            for f in reversed(fbs[-3:]):
                st.markdown(f'<div class="feedback-card"><b style="color:#ffff00">{f["valutazione"]}</b><br>{f.get("richieste","")}</div>', unsafe_allow_html=True)
            if fbs and PDF_ENABLED:
                st.download_button("Scarica PDF Feedback", generate_pdf([f["valutazione"] for f in fbs], "Feedback"), "feedback.pdf")
            if st.button("Svuota Feedback"): save_json("feedback_webinar.json", []); st.rerun()

        with c3:
            st.write("**Upload:**")
            up = st.file_uploader("Video MP4", type=['mp4'])
            if up and st.button("CARICA"): s3.upload_fileobj(up, BUCKET, up.name); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
