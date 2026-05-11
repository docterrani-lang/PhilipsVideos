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

# --- PHILIPS BRAND DESIGN (CSS AGGIORNATO) ---
st.markdown("""
    <style>
    .stApp { background-color: #0066a1; color: #ffffff; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* Messaggi di Errore/Successo personalizzati per sfondo blu */
    .stAlert { background-color: rgba(255, 255, 255, 0.9) !important; color: #0066a1 !important; border: none !important; }
    .stAlert p { color: #0066a1 !important; font-weight: bold; }
    
    /* Titoli e Testi */
    h1, h2, h3, h4, span, label, p { color: #ffffff !important; }
    .stMarkdown { color: #ffffff !important; }

    /* Input Fields */
    div.stTextInput > div > div > input { background-color: #ffffff !important; color: #0066a1 !important; }
    div.stTextArea > div > div > textarea { background-color: #ffffff !important; color: #0066a1 !important; }
    div.stSelectbox > div > div { background-color: #ffffff !important; color: #0066a1 !important; }

    /* Pulsanti */
    div.stButton > button { 
        background-color: #ffffff !important; color: #0066a1 !important; 
        border-radius: 4px; font-weight: bold; height: 45px; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #e6e6e6 !important; }
    
    /* Box Admin */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
        margin-top: 20px;
    }
    
    /* Nascondi download video */
    video::-internal-media-controls-download-button { display:none; }
    </style>
    """, unsafe_allow_html=True)

# --- CONNESSIONI ---
ADMIN_USER = "Admin"
ADMIN_PASS = "Philips!"
AUTHORIZED_EMAILS = st.secrets.get("AUTHORIZED_EMAILS", [])

s3 = boto3.client("s3", 
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]
REQ_FILE = "richieste_accesso.json"
FEEDBACK_FILE = "feedback_webinar.json"

# --- FUNZIONI DATI ---
def load_json(filename):
    try:
        res = s3.get_object(Bucket=BUCKET, Key=filename)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(filename, data):
    s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))

# --- LOGICA DI ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"
if "show_feedback" not in st.session_state: st.session_state.show_feedback = False

# LOGIN STEP 1 & 2 (Centrati)
if st.session_state.login_step in ["step1", "step2"]:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        
        if st.session_state.login_step == "step1":
            st.title("Spectral CT Portal")
            uid = st.text_input("Username o Email")
            if st.button("PROSEGUI"):
                if uid == ADMIN_USER:
                    st.session_state.temp_user = uid
                    st.session_state.login_step = "step2"; st.rerun()
                elif uid in AUTHORIZED_EMAILS:
                    otp = str(random.randint(100000, 999999))
                    st.session_state.generated_otp = otp
                    st.session_state.temp_user = uid
                    # Invio mail (riutilizza la tua funzione send_otp qui)
                    # if send_otp(uid, otp): ...
                    st.session_state.login_step = "step2"; st.rerun()
                else:
                    st.error("Utente non autorizzato.")
                    if st.button("INVIA RICHIESTA DI ACCESSO"):
                        reqs = load_json(REQ_FILE)
                        if uid not in [r['email'] for r in reqs]:
                            reqs.append({"email": uid, "date": datetime.now().strftime("%Y-%m-%d")})
                            save_json(REQ_FILE, reqs)
                            st.success("Richiesta inviata.")
        
        elif st.session_state.login_step == "step2":
            st.title("Verifica")
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("CONFERMA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"; st.rerun()
                else: st.error("Dati errati.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    
    # GESTIONE POPUP FEEDBACK
    if st.session_state.show_feedback:
        st.title("La tua opinione è importante")
        st.write("Aiutaci a migliorare i nostri contenuti Spectral CT.")
        
        with st.form("feedback_form"):
            valutazione = st.select_slider("Quanto hai trovato utile questo webinar?", 
                                          options=["Inutile", "Poco utile", "Suff", "Utile", "Molto utile"])
            interessi = st.text_area("Quali altri argomenti vorresti approfondire?")
            
            if st.form_submit_button("INVIA E ESCI"):
                feedbacks = load_json(FEEDBACK_FILE)
                feedbacks.append({
                    "user": st.session_state.temp_user,
                    "valutazione": valutazione,
                    "richieste": interessi,
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_json(FEEDBACK_FILE, feedbacks)
                st.session_state.login_step = "step1"
                st.session_state.show_feedback = False
                st.rerun()
        if st.button("Annulla"):
            st.session_state.show_feedback = False; st.rerun()
        st.stop()

    # LAYOUT PRINCIPALE
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    c_vid, c_list = st.columns([3, 1])

    with c_list:
        st.subheader("Webinar Library")
        videos = [] # list_videos() - usa la tua funzione qui
        for v in videos:
            if st.button(f"▶ {v.replace('.mp4','')}", key=v):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("🚪 LOGOUT E FEEDBACK"):
            st.session_state.show_feedback = True; st.rerun()

    with c_vid:
        if "active_video" in st.session_state:
            st.subheader(v.replace('.mp4',''))
            # st.video(get_signed_url(...)) - usa la tua funzione qui
        else: st.info("Seleziona un contenuto a destra.")

        # --- ADMIN PANEL ---
        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙️ Administration & Insights")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.write("**Richieste Accesso:**")
                # Visualizza richieste...
            with a2:
                st.write("**Feedback Ricevuti:**")
                fbs = load_json(FEEDBACK_FILE)
                for f in fbs[-3:]: # Mostra ultimi 3
                    st.caption(f"{f['valutazione']} - {f['user']}")
            with a3:
                st.write("**Carica Webinar:**")
                # Uploader...
            st.markdown('</div>', unsafe_allow_html=True)
