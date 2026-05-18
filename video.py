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
# Se reportlab è presente nel tuo requirements.txt, i tasti di download appariranno automaticamente
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="PHILIPS SPECTRAL CT WEBINAR", layout="wide")

# --- INIEZIONE METADATI PWA (Rende l'app installabile su iOS e Android) ---
st.markdown("""
    <script>
    // 1. Configurazione dinamica del Manifest PWA
    const myManifest = {
      "short_name": "Spectral CT",
      "name": "Philips Spectral CT Webinar",
      "icons": [
        {
          "src": "https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png",
          "type": "image/png",
          "sizes": "512x512"
        }
      ],
      "start_url": ".",
      "background_color": "#0066a1",
      "theme_color": "#0066a1",
      "display": "standalone",
      "orientation": "portrait"
    };

    const stringManifest = JSON.stringify(myManifest);
    const blob = new Blob([stringManifest], {type: 'application/json'});
    const manifestURL = URL.createObjectURL(blob);
    
    // Append dell'elemento manifest nell'head HTML
    let link = document.createElement('link');
    link.rel = 'manifest';
    link.href = manifestURL;
    document.head.appendChild(link);

    // 2. Ottimizzazioni specifiche per iOS (Modalità App a tutto schermo su iPhone)
    let metaApple = document.createElement('meta');
    metaApple.name = 'apple-mobile-web-app-capable';
    metaApple.content = 'yes';
    document.head.appendChild(metaApple);
    
    let metaAppleStatus = document.createElement('meta');
    metaAppleStatus.name = 'apple-mobile-web-app-status-bar-style';
    metaAppleStatus.content = 'black-translucent';
    document.head.appendChild(metaAppleStatus);
    </script>
    """, unsafe_allow_html=True)

# --- CSS DEFINITIVO (Risolve i bottoni vuoti/bianchi e adatta i testi) ---
st.markdown("""
    <style>
    /* Sfondo e Font Generale */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* Testi e Label in Bianco */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small {
        color: #ffffff !important;
    }

    /* FIX BOTTONI: Forza sfondo bianco e rimuove bordi */
    button, div.stButton > button, div.stFormSubmitButton > button, 
    div.stDownloadButton > button, [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px !important;
    }

    /* FORZA COLORE TESTO BLU PHILIPS SU QUALSIASI ELEMENTO INTERNO AI BOTTONI */
    button *, div.stButton > button *, div.stDownloadButton > button *, [data-testid="stFileUploadDropzone"] button * {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
    }

    /* Stile personalizzato per l'area di Caricamento Video (Dropzone) */
    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed rgba(255,255,255,0.4) !important;
        background-color: rgba(255,255,255,0.05) !important;
    }
    
    /* Testi informativi generici dell'uploader in bianco per contrasto */
    [data-testid="stFileUploadDropzone"] section div div {
        color: #ffffff !important;
    }

    /* Elementi Interfaccia (Pannello Admin, Username Giallo e Card Feedback) */
    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
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
    
    /* Input di testo scuri all'interno per corretta leggibilità */
    input, textarea { color: #004d7a !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONE UTILI GENERAZIONE PDF ---
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

# --- CONNESSIONE CLOUD STORAGE (S3/R2) ---
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

def save_json(f, d): 
    s3.put_object(Bucket=BUCKET, Key=f, Body=json.dumps(d))

# --- GESTIONE STATO NAVIGAZIONE (LOGIN) ---
if "login_step" not in st.session_state: 
    st.session_state.login_step = "step1"

# STEP 1: SCHERMATA INSERIMENTO USERNAME / EMAIL
if st.session_state.login_step == "step1":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        st.title("Accesso Portale")
        uid = st.text_input("Username o Email")
        if st.button("PROSEGUI"):
            if uid == "Admin" or uid in st.secrets.get("AUTHORIZED_EMAILS", []):
                st.session_state.temp_user = uid
                st.session_state.login_step = "step2"
                st.rerun()

# STEP 2: SCHERMATA VERIFICA PASSWORD / CODICE OTP
elif st.session_state.login_step == "step2":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.title("Verifica Identità")
        st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
        pwd = st.text_input("Codice o Password", type="password")
        if st.button("CONFERMA"):
            # Gestione ruoli automatica
            st.session_state.role = "admin" if st.session_state.temp_user == "Admin" else "user"
            st.session_state.login_step = "authorized"
            st.rerun()

# --- AREA PORTALE AUTORIZZATA ---
elif st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    
    # [Qui puoi inserire la visualizzazione della tua Libreria Video per gli utenti standard]
    
    # --- PANNELLO AMMINISTRATORE (Disponibile solo se role == admin) ---
    if st.session_state.role == "admin":
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        # Colonna 1: Gestione Richieste Registrazione
        with c1:
            st.markdown("#### 📩 Richieste Accesso")
            reqs = load_json("richieste_accesso.json")
            for r in reqs: st.text(f"• {r.get('email', 'N/A')}")
            
            if reqs and PDF_ENABLED:
                pdf_req = generate_pdf([f"{r['email']} ({r.get('date','')})" for r in reqs], "Richieste Registrazione")
                st.download_button("Scarica PDF Richieste", data=pdf_req, file_name="richieste.pdf")
            if st.button("Svuota Lista Richieste"):
                save_json("richieste_accesso.json", [])
                st.rerun()
                
        # Colonna 2: Visualizzazione e Cancellazione Feedback
        with c2:
            st.markdown("#### 💬 Feedback Ricevuti")
            fbs = load_json("feedback_webinar.json")
            for f in reversed(fbs[-5:]): # Mostra gli ultimi 5 feedback caricati
                st.markdown(f"""<div class="feedback-card">
                    <b style="color:#ffff00">{f['valutazione']}</b> - <i>{f['user']}</i><br>
                    <span>{f.get('richieste', 'Nessun commento extra')}</span>
                </div>""", unsafe_allow_html=True)
                
            if fbs and PDF_ENABLED:
                f_data = [f"[{f['valutazione']}] {f['user']}: {f.get('richieste','')}" for f in fbs]
                pdf_feed = generate_pdf(f_data, "Report Feedback Webinar")
                st.download_button("Scarica PDF Feedback", data=pdf_feed, file_name="feedback.pdf")
            if st.button("Svuota Tutti i Feedback"):
                save_json("feedback_webinar.json", [])
                st.rerun()

        # Colonna 3: Upload dei file multimediali su R2
        with c3:
            st.markdown("#### 📤 Caricamento Video")
            up = st.file_uploader("Seleziona file MP4", type=['mp4'], key="uploader_pwa")
            if up and st.button("ESEGUI CARICAMENTO"):
                with st.spinner("Caricamento sul Cloud..."):
                    s3.upload_fileobj(up, BUCKET, up.name)
                    st.success("Video caricato correttamente!")
                    st.rerun()
                    
        st.markdown('</div>', unsafe_allow_html=True)
