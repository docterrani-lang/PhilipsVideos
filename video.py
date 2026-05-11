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

# --- PHILIPS BRAND DESIGN (CSS DEFINITIVO) ---
st.markdown("""
    <style>
    /* 1. Sfondo e Testi base: BIANCHI su BLU */
    .stApp { background-color: #0066a1; color: #ffffff !important; }
    html, body, [class*="st-"], .stMarkdown, p, span, label { 
        font-family: 'Calibri', sans-serif; 
        color: #ffffff !important; 
    }
    
    /* 2. Testi Evidenziati: BLU PHILIPS su fondo chiaro */
    /* Usiamo una classe specifica per i titoli o box evidenziati */
    .highlight-box { 
        color: #0066a1 !important; 
        background-color: #e6f3ff; 
        padding: 5px 10px; 
        border-radius: 4px; 
        font-weight: bold; 
    }
    
    /* 3. Pulsanti: SFONDO BIANCO, TESTO BLU PHILIPS */
    div.stButton > button { 
        background-color: #ffffff !important; 
        color: #0066a1 !important; 
        border-radius: 4px; font-weight: bold; height: 45px; width: 100%; border: none;
        font-size: 16px;
    }
    div.stButton > button:hover { background-color: #e6e6e6 !important; color: #004d7a !important; }

    /* 4. Input Fields: Testo BLU su fondo BIANCO */
    div.stTextInput > div > div > input { background-color: #ffffff !important; color: #0066a1 !important; }
    div.stTextArea > div > div > textarea { background-color: #ffffff !important; color: #0066a1 !important; }
    
    /* Radio Buttons (Feedback): Testi Bianchi */
    div[data-testid="stMarkdownContainer"] > p { color: #ffffff !important; }

    /* Alert Box: Forza testo BLU su sfondo quasi bianco */
    .stAlert { background-color: rgba(255, 255, 255, 0.95) !important; border: none !important; }
    .stAlert p { color: #0066a1 !important; font-weight: bold; }

    /* Pannello Admin */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
    }
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

# --- FUNZIONI CORE ---
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
        res = s3.get_object(Bucket=BUCKET, Key=filename)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(filename, data):
    s3.put_object(Bucket=BUCKET, Key=filename, Body=json.dumps(data))

def list_videos():
    try:
        res = s3.list_objects_v2(Bucket=BUCKET)
        return [obj['Key'] for obj in res.get('Contents', []) if obj['Key'].endswith('.mp4')]
    except: return []

def get_signed_url(key):
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

# --- LOGICA DI ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"
if "show_feedback" not in st.session_state: st.session_state.show_feedback = False

# STEP 1 & 2
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
                    if send_otp(uid, otp):
                        st.session_state.login_step = "step2"; st.rerun()
                else:
                    st.error("Utente non autorizzato.")
                    if st.button("INVIA RICHIESTA DI ACCESSO"):
                        reqs = load_json(REQ_FILE)
                        reqs.append({"email": uid, "date": datetime.now().strftime("%Y-%m-%d")})
                        save_json(REQ_FILE, reqs)
                        st.success("Richiesta inviata correttamente.")
        
        elif st.session_state.login_step == "step2":
            st.title("Verifica")
            # NOME UTENTE IN GIALLO
            st.markdown(f"Accesso per: <span style='color: #ffff00; font-weight: bold; font-size: 22px;'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
            st.write("Inserisci il codice ricevuto o la password:")
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("CONFERMA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"; st.rerun()
                else: st.error("Credenziali non valide.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    
    # POPUP FEEDBACK
    if st.session_state.show_feedback:
        st.title("Valutazione Webinar")
        st.write("Aiutaci a migliorare selezionando un'opzione:")
        
        with st.form("feedback_form"):
            valutazione = st.radio("Quanto hai trovato utile il contenuto?", 
                                  options=["Inutile", "Poco utile", "Sufficiente", "Utile", "Molto utile"], 
                                  index=3)
            interessi = st.text_area("Suggerimenti o interessi futuri:")
            if st.form_submit_button("INVIA E CHIUDI SESSIONE"):
                feedbacks = load_json(FEEDBACK_FILE)
                feedbacks.append({
                    "user": st.session_state.temp_user, "valutazione": valutazione,
                    "richieste": interessi, "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_json(FEEDBACK_FILE, feedbacks)
                st.session_state.login_step = "step1"
                st.session_state.show_feedback = False
                st.rerun()
        if st.button("Annulla e resta nel portale"):
            st.session_state.show_feedback = False; st.rerun()
        st.stop()

    # LAYOUT PRINCIPALE
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    c_vid, c_list = st.columns([3, 1])

    with c_list:
        st.subheader("Webinar Library")
        videos = list_videos()
        for v in videos:
            if st.button(f"▶ {v.replace('.mp4','')}", key=v):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("🚪 LOGOUT"):
            st.session_state.show_feedback = True; st.rerun()

    with c_vid:
        if "active_video" in st.session_state:
            # Titolo video evidenziato: Testo BLU PHILIPS su fondo azzurro chiaro
            st.markdown(f"### <span class='highlight-box'>In riproduzione: {st.session_state.active_video.replace('.mp4', '')}</span>", unsafe_allow_html=True)
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("Seleziona un video dalla lista a destra per iniziare.")

        # --- ADMIN PANEL ---
        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙️ Pannello Amministratore")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("<p style='color: #00d4ff; font-weight: bold;'>Richieste Accesso</p>", unsafe_allow_html=True)
                reqs = load_json(REQ_FILE)
                for r in reqs: st.text(f"• {r['email']}")
                if reqs and st.button("🗑️ Svuota"):
                    save_json(REQ_FILE, []); st.rerun()
            with a2:
                st.markdown("<p style='color: #00d4ff; font-weight: bold;'>Feedback Ricevuti</p>", unsafe_allow_html=True)
                fbs = load_json(FEEDBACK_FILE)
                for f in fbs[-3:]: st.markdown(f"<span style='font-size:12px; color: #ffffff;'>{f['valutazione']} - {f['user']}</span>", unsafe_allow_html=True)
            with a3:
                st.markdown("<p style='color: #00d4ff; font-weight: bold;'>Nuovo Upload</p>", unsafe_allow_html=True)
                up = st.file_uploader("Scegli MP4", type=['mp4'])
                if up and st.button("CARICA"):
                    s3.upload_fileobj(up, BUCKET, up.name); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
