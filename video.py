import streamlit as st
import boto3
from botocore.config import Config

# --- CONNESSIONE R2 ---
s3 = boto3.client(
    "s3",
    endpoint_url=st.secrets["R2_ENDPOINT"],
    aws_access_key_id=st.secrets["R2_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["R2_SECRET_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

BUCKET = st.secrets["BUCKET_NAME"]

# --- CSS PROTEZIONE ---
st.markdown("""
    <style> video::-internal-media-controls-download-button { display:none; } </style>
    <script> document.addEventListener('contextmenu', event => event.preventDefault()); </script>
    """, unsafe_allow_html=True)

# --- FUNZIONI ---
def list_videos():
    response = s3.list_objects_v2(Bucket=BUCKET)
    return [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.mp4')]

def upload_video(file):
    # R2 accetta tranquillamente 300MB
    s3.upload_fileobj(file, BUCKET, file.name)
    st.success("Caricamento completato!")

def get_signed_url(key):
    # Genera un link sicuro che dura 1 ora
    return s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET, 'Key': key},
        ExpiresIn=3600
    )

# --- UI ---
st.title("📽️ Video Storage 300MB+")

if "admin" not in st.session_state: st.session_state.admin = False

with st.sidebar:
    if not st.session_state.admin:
        u = st.text_input("Admin User")
        p = st.text_input("Admin Pass", type="password")
        if st.button("Login"):
            if u == st.secrets["ADMIN_USER"] and p == st.secrets["ADMIN_PASS"]:
                st.session_state.admin = True
                st.rerun()
    else:
        if st.button("Logout"):
            st.session_state.admin = False
            st.rerun()

videos = list_videos()

if st.session_state.admin:
    st.header("🛠️ Pannello Admin")
    up = st.file_uploader("Carica Video (senza limiti)", type=['mp4'])
    if up and st.button("Inizia Upload"):
        with st.spinner("Trasferimento al cloud in corso..."):
            upload_video(up)
            st.rerun()
    
    st.divider()
    for v in videos:
        c1, c2 = st.columns([4,1])
        c1.write(v)
        if c2.button("Elimina", key=v):
            s3.delete_object(Bucket=BUCKET, Key=v)
            st.rerun()
else:
    st.header("📺 Streaming")
    if videos:
        sel = st.selectbox("Seleziona video", videos)
        url = get_signed_url(sel)
        st.video(url)
    else:
        st.info("Nessun video presente.")
