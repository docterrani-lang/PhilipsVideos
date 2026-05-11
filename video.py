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

# --- CSS DEFINITIVO: FIX BOTTONI ADMIN + FEEDBACK + COLORI ---
st.markdown("""
    <style>
    /* Sfondo e Font */
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    /* Testi base bianchi */
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small {
        color: #ffffff !important;
    }

    /* TUTTI I PULSANTI (Normali, Form, File Uploader, Admin) */
    div.stButton > button, div.stFormSubmitButton > button, [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        color: #0066a1 !important;
        font-weight: bold !important;
        min-height: 40px;
    }
    
    /* Forza testo blu dentro ogni tipo di bottone */
    div.stButton > button div p, 
    div.stButton > button span, 
    div.stFormSubmitButton > button div p, 
    div.stFormSubmitButton > button span,
    [data-testid="stFileUploadDropzone"] button span {
        color: #0066a1 !important;
        font-weight: bold !important;
    }

    /* Username in GIALLO */
    .user-yellow {
        color: #ffff00 !important;
        font-weight: bold !important;
        font-size: 22px !important;
        margin-bottom: 10px;
        display: block;
    }

    /* Box Riproduzione Video (Blu su Azzurro) */
    .highlight-box {
        background-color: #e6f3ff;
        color: #0066a1 !important;
        padding: 15px;
        border-radius: 5px;
        font-weight: bold;
        margin-bottom: 20px;
        border-left: 6px solid #ffff00;
    }
    .highlight-box * { color: #0066a1 !important; }

    /* Input Fields */
    input, textarea { color: #004d7a !important; }

    /* Pannello Admin e Feedback Item */
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3);
        margin-top: 30px;
    }
    .feedback-card {
        background-color: rgba(255, 255, 255, 0.15);
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #ffff00;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONNESSIONI E SEGRETI ---
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

# --- FUNZIONI UTILI ---
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
                        reqs = load_json("richieste_accesso.json")
                        reqs.append({"email": uid, "date": datetime.now().strftime("%Y-%m-%d")})
                        save_json("richieste_accesso.json", reqs); st.success("Richiesta inviata.")
        
        elif st.session_state.login_step == "step2":
            st.title("Verifica")
            st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("CONFERMA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.get("generated_otp")):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"; st.rerun()
                else: st.error("Dati non corretti.")
    st.stop()

# --- AREA PORTALE ---
if st.session_state.login_step == "authorized":
    
    if st.session_state.show_feedback:
        st.title("La tua opinione")
        with st.form("feedback_final"):
            voto = st.radio("Valutazione:", ["Inutile", "Poco utile", "Sufficiente", "Utile", "Molto utile"], index=3)
            testo = st.text_area("Cosa ne pensi? Suggerimenti:")
            if st.form_submit_button("INVIA E CHIUDI"):
                fbs = load_json("feedback_webinar.json")
                fbs.append({"user": st.session_state.temp_user, "valutazione": voto, "richieste": testo, "data": datetime.now().strftime("%Y-%m-%d %H:%M")})
                save_json("feedback_webinar.json", fbs)
                st.session_state.login_step = "step1"; st.session_state.show_feedback = False; st.rerun()
        if st.button("Annulla"): st.session_state.show_feedback = False; st.rerun()
        st.stop()

    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    c_vid, c_list = st.columns([3, 1])

    with c_list:
        st.subheader("Webinar Library")
        vids = list_videos()
        for v in vids:
            if st.button(f"▶ {v.replace('.mp4','')}", key=v):
                st.session_state.active_video = v
        st.divider()
        if st.button("🚪 LOGOUT"): st.session_state.show_feedback = True; st.rerun()

    with c_vid:
        if "active_video" in st.session_state:
            st.markdown(f"<div class='highlight-box'>In riproduzione: {st.session_state.active_video.replace('.mp4', '')}</div>", unsafe_allow_html=True)
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("👈 Seleziona un contenuto dalla lista.")

        # --- ADMIN ---
        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙️ Controllo Amministratore")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("#### 📩 Richieste Accesso")
                r_list = load_json("richieste_accesso.json")
                for r in r_list: st.text(f"• {r['email']}")
                if r_list and st.button("Svuota richieste"): save_json("richieste_accesso.json", []); st.rerun()
            with a2:
                st.markdown("#### 💬 Feedback completi")
                f_list = load_json("feedback_webinar.json")
                for f in reversed(f_list[-5:]): # Ultimi 5 feedback
                    st.markdown(f"""<div class="feedback-card">
                        <b style="color:#ffff00">{f['valutazione']}</b> - <i>{f['user']}</i><br>
                        <span style="color:white">{f.get('richieste', '')}</span>
                    </div>""", unsafe_allow_html=True)
            with a3:
                st.markdown("#### 📤 Carica Video")
                f_up = st.file_uploader("File MP4", type=['mp4'])
                if f_up and st.button("Esegui Caricamento"):
                    s3.upload_fileobj(f_up, BUCKET, f_up.name); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
