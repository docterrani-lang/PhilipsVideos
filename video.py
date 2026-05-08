import streamlit as st
import boto3
from botocore.config import Config

# --- 1. CONFIGURAZIONE E WHITELIST ---
# Elenco delle email autorizzate a vedere i video
AUTHORIZED_USERS = [
    "utente1@gmail.com",
    "cliente.speciale@azienda.it",
    "tua.email@gmail.com" # Aggiungi la tua email!
]

# Credenziali Admin (per caricare/cancellare)
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]

# Connessione R2
s3 = boto3.client(
    "s3",
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto"
)
BUCKET = st.secrets["BUCKET_NAME"]

# --- 2. FUNZIONI DI SERVIZIO ---
def list_videos():
    res = s3.list_objects_v2(Bucket=BUCKET)
    return [obj['Key'] for obj in res.get('Contents', []) if obj['Key'].endswith('.mp4')]

def get_signed_url(key):
    return s3.generate_presigned_url('get_object', Params={'Bucket': BUCKET, 'Key': key}, ExpiresIn=3600)

# --- 3. CONTROLLO IDENTITÀ (IL BUTTAFUORI) ---
# Recupera l'utente loggato su Streamlit Cloud
user_info = st.user

def check_auth():
    if not user_info or user_info.email not in AUTHORIZED_USERS:
        st.error("🚫 Accesso negato. La tua identità non è autorizzata a visualizzare questo portale.")
        st.info("Assicurati di aver effettuato l'accesso a Streamlit con l'email corretta.")
        st.stop() # Blocca l'esecuzione di tutto il resto dello script

# --- 4. INTERFACCIA ---

# Se l'utente non è loggato con l'email della whitelist, lo script si ferma qui
check_auth()

# Se arriviamo qui, l'utente è autorizzato. Mostriamo l'interfaccia.
st.title("🔐 Portale Video Riservato")
st.write(f"Benvenuto, **{user_info.email}**")

# Gestione Login AMMINISTRATORE (opzionale, per gestire i file)
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar:
    st.header("Area Amministrativa")
    if not st.session_state.is_admin:
        u = st.text_input("Username Admin")
        p = st.text_input("Password Admin", type="password")
        if st.button("Login Admin"):
            if u == ADMIN_USER and p == ADMIN_PASS:
                st.session_state.is_admin = True
                st.rerun()
    else:
        st.success("Modalità Admin Attiva")
        if st.button("Logout Admin"):
            st.session_state.is_admin = False
            st.rerun()

# --- 5. LOGICA VISUALIZZAZIONE / GESTIONE ---
videos = list_videos()

if st.session_state.is_admin:
    st.subheader("🛠️ Gestione File (Admin)")
    up = st.file_uploader("Carica nuovo video", type=['mp4'])
    if up and st.button("Carica su R2"):
        s3.upload_fileobj(up, BUCKET, up.name)
        st.success("Caricato!")
        st.rerun()
    
    for v in videos:
        c1, c2 = st.columns([4,1])
        c1.write(v)
        if c2.button("Elimina", key=v):
            s3.delete_object(Bucket=BUCKET, Key=v)
            st.rerun()
else:
    # Vista Utente Normale
    if videos:
        sel = st.selectbox("Scegli un video da riprodurre", videos)
        url = get_signed_url(sel)
        st.video(url)
    else:
        st.info("Nessun video disponibile nel tuo archivio.")
