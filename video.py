import streamlit as st
import boto3
from botocore.config import Config
import smtplib
import random
import json
from email.message import EmailMessage
from datetime import datetime
import io

# Importante: se non vuoi installare reportlab subito, 
# questo blocco evita che l'app crashi se la libreria manca
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- CSS DEFINITIVO ---
st.markdown("""
    <style>
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small { color: #ffffff !important; }

    /* Pulsanti Bianchi con Testo Blu */
    div.stButton > button, div.stFormSubmitButton > button, [data-testid="stFileUploadDropzone"] button, .stDownloadButton > button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px;
        width: 100%;
    }
    
    /* Forza testo blu ed elimina icone/testi strani */
    div.stButton > button div p, div.stButton > button span, .stDownloadButton > button span {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
    }

    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
    .highlight-box { background-color: #e6f3ff; color: #0066a1 !important; padding: 15px; border-radius: 5px; border-left: 6px solid #ffff00; margin-bottom: 20px; }
    .highlight-box * { color: #0066a1 !important; }
    
    .admin-box { background-color: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); margin-top: 30px; }
    .feedback-card { background-color: rgba(255, 255, 255, 0.15); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #ffff00; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONE GENERAZIONE PDF ---
def generate_pdf(data, title):
    if not PDF_AVAILABLE:
        return None
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, title)
    p.setFont("Helvetica", 10)
    y = 720
    for item in data:
        p.drawString(100, y, f"- {item}")
        y -= 20
        if y < 50:
            p.showPage()
            y = 750
    p.save()
    buffer.seek(0)
    return buffer

# --- LOGICA S3 / CONNESSIONI ---
# (Assicurati che i tuoi st.secrets siano configurati correttamente)
s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]

def load_json(filename):
    try:
        res = s3.get_object(Bucket=BUCKET, Key=filename)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(filename, data):
    s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))

# --- GESTIONE ACCESSO (SINTESI) ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"

# [Mantenere qui la tua logica di Step 1 e Step 2 come visto in precedenza]

if st.session_state.get("login_step") == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # Area Webinar... (omessa per brevità)

    # --- PANNELLO ADMIN ---
    if st.session_state.get("role") == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        
        a1, a2, a3 = st.columns(3)
        
        with a1:
            st.markdown("#### 📩 Richieste Accesso")
            r_list = load_json("richieste_accesso.json")
            for r in r_list: st.text(f"• {r['email']}")
            
            if r_list and PDF_AVAILABLE:
                pdf_req = generate_pdf([f"{r['email']} ({r['date']})" for r in r_list], "Richieste Registrazione")
                st.download_button("Scarica PDF Richieste", data=pdf_req, file_name="richieste.pdf")
            
            if r_list and st.button("Svuota Lista Richieste"):
                save_json("richieste_accesso.json", [])
                st.rerun()

        with a2:
            st.markdown("#### 💬 Feedback Utenti")
            f_list = load_json("feedback_webinar.json")
            for f in reversed(f_list[-5:]):
                st.markdown(f"""<div class="feedback-card">
                    <b style="color:#ffff00">{f['valutazione']}</b> - <i>{f['user']}</i><br>
                    <span>{f.get('richieste', 'Nessun commento')}</span>
                </div>""", unsafe_allow_html=True)
            
            if f_list and PDF_AVAILABLE:
                f_txt = [f"[{f['valutazione']}] {f['user']}: {f.get('richieste','')}" for f in f_list]
                pdf_feed = generate_pdf(f_txt, "Report Feedback")
                st.download_button("Scarica PDF Feedback", data=pdf_feed, file_name="feedback.pdf")
                
            if f_list and st.button("Svuota Tutti i Feedback"):
                save_json("feedback_webinar.json", [])
                st.rerun()

        with a3:
            st.markdown("#### 📤 Gestione Video")
            # Qui il file uploader caricherà su R2
            f_up = st.file_uploader("Carica nuovo MP4", type=['mp4'])
            if f_up and st.button("Avvia Upload"):
                s3.upload_fileobj(f_up, BUCKET, f_up.name)
                st.success("Video caricato!")
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)
