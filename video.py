import streamlit as st
import boto3
from botocore.config import Config

# --- CONFIGURAZIONE ---
AUTHORIZED_EMAILS = ["utente1@gmail.com", "utente2@gmail.com"] # Email autorizzate
ADMIN_USER = "Admin"
ADMIN_PASS = "Philips!"

# Connessione Cloudflare R2
s3 = boto3.client(
    "s3",
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]

# --- FUNZIONI ---
def list_videos():
    res = s3.list_objects_v2(Bucket=BUCKET)
    return [obj['Key'] for obj in res.get('Contents', []) if obj['Key'].endswith('.mp4')]

def get_signed_url(key):
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

# --- GESTIONE ACCESSO ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None # "admin" o "user"

# PAGINA DI LOGIN (Viene mostrata se non sei autenticato)
if not st.session_state.authenticated:
    st.title("🔐 Accesso Riservato")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    
    if st.button("Accedi"):
        # 1. Controllo se è l'Admin (Philips!)
        if u == ADMIN_USER and p == ADMIN_PASS:
            st.session_state.authenticated = True
            st.session_state.role = "admin"
            st.rerun()
        
        # 2. Se non è admin, controllo l'email di Streamlit Cloud
        else:
            # Recuperiamo l'email di chi è loggato nel browser su Streamlit
            current_user_email = st.user.email if st.user else None
            
            if current_user_email in AUTHORIZED_EMAILS:
                st.session_state.authenticated = True
                st.session_state.role = "user"
                st.rerun()
            else:
                st.error("Identità non riconosciuta o credenziali errate.")
                if not current_user_email:
                    st.info("Nota: Per l'accesso utente devi essere loggato su Streamlit Cloud.")
                else:
                    st.warning(f"L'email {current_user_email} non è abilitata.")
    st.stop() # Blocca tutto il resto finché non sei loggato

# --- SE ARRIVIAMO QUI, L'UTENTE È DENTRO ---
st.title("🎬 Portale Video")
if st.session_state.role == "admin":
    st.sidebar.success("Accesso: AMMINISTRATORE")
else:
    st.sidebar.info(f"Accesso: UTENTE ({st.user.email})")

if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.role = None
    st.rerun()

# --- LOGICA VIDEO ---
videos = list_videos()

if st.session_state.role == "admin":
    # --- SEZIONE ADMIN (Caricamento e Cancellazione) ---
    st.subheader("🛠️ Gestione Contenuti")
    up = st.file_uploader("Carica Video", type=['mp4'])
    if up and st.button("Upload"):
        with st.spinner("Caricamento..."):
            s3.upload_fileobj(up, BUCKET, up.name)
            st.success("Video caricato!")
            st.rerun()
    
    st.divider()
    for v in videos:
        c1, c2 = st.columns([4,1])
        c1.write(v)
        if c2.button("Elimina", key=v):
            s3.delete_object(Bucket=BUCKET, Key=v)
            st.rerun()
else:
    # --- SEZIONE UTENTE (Solo Visualizzazione) ---
    if videos:
        sel = st.selectbox("Seleziona video", videos)
        url = get_signed_url(sel)
        st.video(url)
    else:
        st.info("Nessun video disponibile.")
