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
    /* Sfondo e Font */
    .stApp { background-color: #0066a1; color: #ffffff; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; color: #ffffff; }
    
    /* Tutti i testi devono essere bianchi */
    label, p, span, .stMarkdown { color: #ffffff !important; }
    
    /* Input Fields con testo scuro per leggibilità */
    div.stTextInput > div > div > input { background-color: #ffffff !important; color: #004d7a !important; }
    div.stTextArea > div > div > textarea { background-color: #ffffff !important; color: #004d7a !important; }
    
    /* Pulsanti bianchi con testo Blu Philips */
    div.stButton > button { 
        background-color: #ffffff !important; 
        color: #004d7a !important; 
        border-radius: 4px; font-weight: bold; height: 45px; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #e6e6e6 !important; }

    /* Radio buttons (Feedback) - Forza testo bianco */
    div[data-testid="stMarkdownContainer"] > p { color: #ffffff !important; }
    
    /* Messaggi di Alert */
    .stAlert { background-color: rgba(255, 255, 255, 0.95) !important; color: #004d7a !important; }
    .stAlert p { color: #004d7a !important; }
    
    /* Admin Box */
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
                        st.success("Richiesta inviata.")
        
        elif st.session_state.login_step == "step2":
            st.title("Verifica")
            # NOME UTENTE IN GIALLO
            st.markdown(f"Utente: <span style='color: yellow; font-weight: bold; font-size: 20px;'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
            st.write("Inserisci le credenziali per accedere:")
            secret = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == ADMIN_USER else "default")
            if st.button("CONFERMA"):
                if (st.session_state.temp_user == ADMIN_USER and secret == ADMIN_PASS) or (secret == st.session_state.generated_otp):
                    st.session_state.role = "admin" if st.session_state.temp_user == ADMIN_USER else "user"
                    st.session_state.login_step = "authorized"; st.rerun()
                else: st.error("Credenziali errate.")
    st.stop()

# --- AREA AUTORIZZATA ---
if st.session_state.login_step == "authorized":
    
    # POPUP FEEDBACK
    if st.session_state.show_feedback:
        st.title("La tua opinione è importante")
        st.write("Aiutaci a migliorare i nostri contenuti.")
        
        with st.form("feedback_form"):
            # FEEDBACK CON VOCI SELEZIONABILI (SOLO 1)
            valutazione = st.radio("Quanto hai trovato utile questo webinar?", 
                                  options=["Inutile", "Poco utile", "Sufficiente", "Utile", "Molto utile"], 
                                  index=3)
            interessi = st.text_area("Argomenti di tuo interesse per i prossimi webinar:")
            
            if st.form_submit_button("INVIA E ESCI"):
                feedbacks = load_json(FEEDBACK_FILE)
                feedbacks.append({
                    "user": st.session_state.temp_user, "valutazione": valutazione,
                    "richieste": interessi, "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_json(FEEDBACK_FILE, feedbacks)
                st.session_state.login_step = "step1"
                st.session_state.show_feedback = False
                st.rerun()
        if st.button("Annulla"):
            st.session_state.show_feedback = False; st.rerun()
        st.stop()

    # LAYOUT PORTALE
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    c_vid, c_list = st.columns([3, 1])

    with c_list:
        st.subheader("Webinar Library")
        videos = list_videos()
        for v in videos:
            if st.button(f"▶ {v.replace('.mp4','')}", key=v):
                st.session_state.active_video = v
        
        st.divider()
        if st.button("🚪 LOGOUT E FEEDBACK"):
            st.session_state.show_feedback = True; st.rerun()

    with c_vid:
        if "active_video" in st.session_state:
            st.subheader(f"In riproduzione: {st.session_state.active_video.replace('.mp4', '')}")
            st.video(get_signed_url(st.session_state.active_video))
        else:
            st.info("👈 Seleziona un webinar dalla lista a destra.")

        # --- ADMIN PANEL ---
        if st.session_state.role == "admin":
            st.markdown('<div class="admin-box">', unsafe_allow_html=True)
            st.subheader("⚙️ Administration & Insights")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.write("**Richieste Accesso:**")
                reqs = load_json(REQ_FILE)
                for r in reqs: st.text(f"• {r['email']}")
                if reqs and st.button("🗑️ Svuota"):
                    save_json(REQ_FILE, []); st.rerun()
            with a2:
                st.write("**Ultimi Feedback:**")
                fbs = load_json(FEEDBACK_FILE)
                for f in fbs[-3:]: st.caption(f"{f['valutazione']} - {f['user']}")
            with a3:
                st.write("**Upload Video:**")
                up = st.file_uploader("MP4", type=['mp4'])
                if up and st.button("PUBBLICA"):
                    s3.upload_fileobj(up, BUCKET, up.name)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
