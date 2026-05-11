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

# --- CSS DEFINITIVO E AGGIORNATO ---
st.markdown("""
    <style>
    /* 1. Sfondo Generale */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* 2. Testi su sfondo Blu: BIANCHI */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3 {
        color: #ffffff !important;
    }

    /* 3. FIX PULSANTI (Inclusi quelli nei Form) */
    /* Applichiamo lo stile a TUTTI i tipi di bottoni Streamlit */
    div.stButton > button, div.stFormSubmitButton > button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        height: 45px !important;
        width: 100% !important;
    }
    
    /* Forza il colore del testo BLU PHILIPS dentro i bottoni */
    div.stButton > button div p, 
    div.stButton > button span, 
    div.stFormSubmitButton > button div p, 
    div.stFormSubmitButton > button span {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* 4. Username in GIALLO */
    .user-yellow {
        color: #ffff00 !important;
        font-weight: bold !important;
        font-size: 20px !important;
    }

    /* 5. Box Riproduzione: TESTO BLU su fondo AZZURRO CHIARO */
    .highlight-box {
        background-color: #e6f3ff;
        color: #0066a1 !important;
        padding: 12px 18px;
        border-radius: 5px;
        font-weight: bold;
        margin-bottom: 15px;
        border-left: 6px solid #ffff00; /* Un tocco di giallo per richiamare il brand */
    }
    /* Forza il testo interno alla box ad essere blu */
    .highlight-box * { color: #0066a1 !important; }

    /* 6. Input Fields */
    input, textarea { color: #004d7a !important; }

    /* Admin Box */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    video::-internal-media-controls-download-button { display:none; }
    </style>
    """, unsafe_allow_html=True)

# --- CONNESSIONI E FUNZIONI ---
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

# --- LOGICA ACCESSO ---
if "login_step" not in st.session_state: st.session_state.login_step = "step1"
if "show_feedback" not in st.session_state: st.session_state.show_feedback = False

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
                    if st.button("INVIA RICHIESTA"):
                        reqs = load_json(REQ_FILE)
                        reqs.append({"email": uid, "date": datetime.now().strftime("%Y-%m-%d")})
                        save_json(REQ_FILE, reqs); st.success("Richiesta inviata.")
        
        elif st.session_state.login_step == "step2":
            st.title("Verifica")
            st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("CONFERMA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"; st.rerun()
                else: st.error("Dati errati.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    
    if st.session_state.show_feedback:
        st.title("Valutazione Webinar")
        with st.form("feedback_form"):
            valutazione = st.radio("Quanto hai trovato utile il contenuto?", 
                                  options=["Inutile", "Poco utile", "Sufficiente", "Utile", "Molto utile"], index=3)
            interessi = st.text_area("Suggerimenti:")
            # Questo è il pulsante che ora si vedrà blu!
            if st.form_submit_button("INVIA E CHIUDI SESSIONE"):
                feedbacks = load_json(FEEDBACK_FILE)
                feedbacks.append({"user": st.session_state.temp_user, "valutazione": valutazione, "richieste": interessi, "data": datetime.now().strftime("%Y-%m-%d %H:%M")})
                save_json(FEEDBACK_FILE, feedbacks)
                st.session_state.login_step = "step1"; st.session_state.show_feedback = False; st.rerun()
        if st.button("Annulla"): st.session_state.show_feedback = False; st.rerun()
        st.stop()

    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    c_vid, c_list = st.columns([3, 1])

    with c_list:
        st.subheader("Webinar Library")
        videos = list_videos()
        for v in videos:
            if st.button(f"▶ {v.replace('.mp4','')}", key=v):
                st.session_state.active_video = v
        st.divider()
        if st.button("🚪 LOGOUT"): st.session_state.show_feedback = True; st.rerun()

    with c_vid:
        if "active_video" in st.session_state:
            st.markdown(f"<div class='highlight-box'>In riproduzione: {st.session_state.active_video.replace('.mp4', '')}</div>", unsafe_allow_html=True)
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("👈 Seleziona un webinar dalla lista.")

        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙️ Pannello Amministratore")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.write("**Richieste Accesso:**")
                reqs = load_json(REQ_FILE)
                for r in reqs: st.text(f"• {r['email']}")
                if reqs and st.button("🗑️ Svuota"): save_json(REQ_FILE, []); st.rerun()
            with a2:
                st.write("**Feedback:**")
                fbs = load_json(FEEDBACK_FILE)
                for f in fbs[-3:]: st.caption(f"{f['valutazione']} - {f['user']}")
            with a3:
                st.write("**Upload Video:**")
                up = st.file_uploader("MP4", type=['mp4'])
                if up and st.button("CARICA"): s3.upload_fileobj(up, BUCKET, up.name); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
