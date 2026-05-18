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

# --- INIEZIONE METADATI PWA (Rende l'app installabile su iOS e Android) ---
st.markdown("""
    <script>
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
    
    let link = document.createElement('link');
    link.rel = 'manifest';
    link.href = manifestURL;
    document.head.appendChild(link);

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

# --- CSS RADICALE (Risolve i bottoni bianchi vuoti e uploader) ---
st.markdown("""
    <style>
    .stApp { background-color: #0066a1 !important; }
    html, body, [class*="st-"] { font-family: 'Calibri', sans-serif; }
    
    .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp small {
        color: #ffffff !important;
    }

    button, div.stButton > button, div.stFormSubmitButton > button, 
    div.stDownloadButton > button, [data-testid="stFileUploadDropzone"] button {
        background-color: #ffffff !important;
        border: none !important;
        border-radius: 4px !important;
        min-height: 40px !important;
    }

    button *, div.stButton > button *, div.stDownloadButton > button *, [data-testid="stFileUploadDropzone"] button * {
        color: #0066a1 !important;
        font-weight: bold !important;
        text-decoration: none !important;
    }

    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed rgba(255,255,255,0.4) !important;
        background-color: rgba(255,255,255,0.05) !important;
    }
    
    [data-testid="stFileUploadDropzone"] section div div {
        color: #ffffff !important;
    }

    .user-yellow { color: #ffff00 !important; font-weight: bold; font-size: 22px; }
    .admin-box { 
        background-color: rgba(255, 255, 255, 0.1); 
        padding: 20px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.3); margin-top: 30px;
    }
    .feedback-card { 
        background-color: rgba(255, 255, 255, 0.15); 
        padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #ffff00; 
    }
    
    input, textarea { color: #004d7a !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNZIONI CORE ---
try:
    s3 = boto3.client("s3", 
        endpoint_url=st.secrets["R2_ENDPOINT"],
        aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
        aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )
    BUCKET = st.secrets["BUCKET_NAME"]
except Exception as e:
    st.error(f"Errore configurazione Cloudflare R2: {e}")

# FUNZIONE INVIATA CODICE OTP VIA EMAIL
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
    except Exception as e:
        st.sidebar.error(f"Errore di invio mail: {e}")
        return False

def load_json(f):
    try:
        res = s3.get_object(Bucket=BUCKET, Key=f)
        return json.loads(res['Body'].read().decode('utf-8'))
    except: return []

def save_json(f, d): 
    try:
        s3.put_object(Bucket=BUCKET, Key=f, Body=json.dumps(d))
    except: pass

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

# --- GESTIONE NAVIGAZIONE ---
if "login_step" not in st.session_state: 
    st.session_state.login_step = "step1"

# STEP 1: LOGIN
if st.session_state.login_step == "step1":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.image("https://www.logosvgpng.com/wp-content/uploads/2021/05/philips-logo-vector.png", width=180)
        st.title("Accesso Portale")
        uid = st.text_input("Username o Email")
        if st.button("PROSEGUI"):
            if uid == "Admin":
                st.session_state.temp_user = uid
                st.session_state.login_step = "step2"
                st.rerun()
            elif uid in st.secrets.get("AUTHORIZED_EMAILS", []):
                otp_code = str(random.randint(100000, 999999))
                st.session_state.generated_otp = otp_code
                st.session_state.temp_user = uid
                
                with st.spinner("Invio del codice OTP in corso..."):
                    if send_otp(uid, otp_code):
                        st.session_state.login_step = "step2"
                        st.rerun()
                    else:
                        st.error("Errore nell'invio dell'email. Controlla la configurazione SMTP.")
            else:
                st.error("Utente non autorizzato.")
                if st.button("INVIA RICHIESTA DI ACCESSO"):
                    reqs = load_json("richieste_accesso.json")
                    reqs.append({"email": uid, "date": datetime.now().strftime("%Y-%m-%d")})
                    save_json("richieste_accesso.json", reqs)
                    st.success("Richiesta di registrazione inoltrata all'amministratore.")

# STEP 2: VERIFICA
elif st.session_state.login_step == "step2":
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.title("Verifica")
        st.markdown(f"Accesso per: <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
        pwd = st.text_input("Codice o Password", type="password" if st.session_state.temp_user == "Admin" else "default")
        if st.button("CONFERMA"):
            if (st.session_state.temp_user == "Admin" and pwd == "Philips!") or (pwd == st.session_state.get("generated_otp")):
                st.session_state.role = "admin" if st.session_state.temp_user == "Admin" else "user"
                st.session_state.login_step = "authorized"
                st.rerun()
            else:
                st.error("Codice o password errati.")

# AREA AUTORIZZATA
elif st.session_state.login_step == "authorized":
    st.title("📽️ PHILIPS SPECTRAL CT WEBINAR")
    st.markdown(f"Benvenuto nel portale medico, <span class='user-yellow'>{st.session_state.temp_user}</span>", unsafe_allow_html=True)
    st.write("---")
    
    # --- LIBRERIA VIDEO DA CLOUDFLARE R2 ---
    try:
        response = s3.list_objects_v2(Bucket=BUCKET)
        video_files = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].lower().endswith('.mp4'):
                    video_files.append(obj['Key'])
        
        if video_files:
            st.subheader("📺 Webinar Disponibili")
            cols_video = st.columns(2)
            for idx, video_key in enumerate(video_files):
                with cols_video[idx % 2]:
                    # Pulizia nome del titolo
                    clean_title = video_key.replace('.mp4', '').replace('_', ' ').upper()
                    st.markdown(f"### 🔹 {clean_title}")
                    
                    video_url = s3.generate_presigned_url('get_object',
                        Params={'Bucket': BUCKET, 'Key': video_key},
                        ExpiresIn=3600
                    )
                    st.video(video_url)
        else:
            st.info("Nessun video attualmente caricato nel bucket Cloudflare R2.")
            
    except Exception as e:
        st.error(f"Impossibile caricare i video dall'infrastruttura Cloud: {e}")

    # --- AREA UTENTE (FEEDBACK) ---
    if st.session_state.role == "user":
        st.write("---")
        st.subheader("✍️ Lascia il tuo Feedback")
        with st.form("feedback_form", clear_on_submit=True):
            rating = st.selectbox("Come valuti questo Webinar?", ["Eccellente", "Ottimo", "Buono", "Sufficiente"])
            comments = st.text_area("Note o richieste aggiuntive:")
            if st.form_submit_button("INVIA FEEDBACK"):
                feedbacks = load_json("feedback_webinar.json")
                feedbacks.append({
                    "user": st.session_state.temp_user,
                    "valutazione": rating,
                    "richieste": comments,
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_json("feedback_webinar.json", feedbacks)
                st.success("Grazie! Il tuo feedback è stato registrato.")

    # --- PANNELLO ADMIN ---
    if st.session_state.role == "admin":
        st.write("---")
        st.markdown('<div class="admin-box">', unsafe_allow_html=True)
        st.subheader("⚙️ Pannello Amministratore")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("#### 📩 Richieste Accesso")
            reqs = load_json("richieste_accesso.json")
            for r in reqs: st.text(f"• {r.get('email', 'N/A')}")
            if reqs and PDF_ENABLED:
                pdf_req = generate_pdf([f"{r['email']} ({r.get('date','')})" for r in reqs], "Richieste Registrazione")
                st.download_button("Scarica PDF Richieste", data=pdf_req, file_name="richieste.pdf")
            if st.button("Svuota Richieste"):
                save_json("richieste_accesso.json", [])
                st.rerun()
                
        with c2:
            st.markdown("#### 💬 Feedback")
            fbs = load_json("feedback_webinar.json")
            for f in reversed(fbs[-3:]):
                st.markdown(f"""<div class="feedback-card">
                    <b style="color:#ffff00">{f['valutazione']}</b> - <i>{f['user']}</i><br>
                    {f.get('richieste', '')}
                </div>""", unsafe_allow_html=True)
            if fbs and PDF_ENABLED:
                f_data = [f"[{f['valutazione']}] {f['user']}: {f.get('richieste','')}" for f in fbs]
                pdf_feed = generate_pdf(f_data, "Report Feedback Webinar")
                st.download_button("Scarica PDF Feedback", data=pdf_feed, file_name="feedback.pdf")
            if st.button("Svuota Feedback"):
                save_json("feedback_webinar.json", [])
                st.rerun()

        with c3:
            st.markdown("#### 📤 Caricamento Video")
            up = st.file_uploader("Seleziona MP4", type=['mp4'], key="uploader_pwa")
            if up and st.button("CARICA ORA"):
                with st.spinner("Caricamento in corso..."):
                    s3.upload_fileobj(up, BUCKET, up.name)
                    st.success("Video caricato!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
