import streamlit as st
from github import Github
import base64

# --- CONFIGURAZIONE E ACCESSO ---
ADMIN_USER = st.secrets["ADMIN_USER"]
ADMIN_PASS = st.secrets["ADMIN_PASS"]
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
VIDEO_PATH = st.secrets["VIDEO_PATH"]

# Connessione a GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- CSS PER PROTEZIONE VIDEO ---
# Nasconde il tasto download e il menu contestuale (tasto destro)
st.markdown("""
    <style>
    video::-internal-media-controls-download-button {
        display:none;
    }
    video::-webkit-media-controls-enclosure {
        overflow:hidden;
    }
    video::-webkit-media-controls-panel {
        width: calc(100% + 30px); 
    }
    </style>
    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
    """, unsafe_allow_html=True)

# --- FUNZIONI GITHUB ---
def get_video_list():
    contents = repo.get_contents(VIDEO_PATH)
    return [f for f in contents if f.name.endswith(('.mp4', '.mov', '.avi'))]

def upload_video(file):
    content = file.read()
    repo.create_file(f"{VIDEO_PATH}/{file.name}", f"Upload {file.name}", content)
    st.success(f"Video {file.name} caricato!")

def delete_video(file_path, sha):
    repo.delete_file(file_path, "Eliminazione video", sha)
    st.warning("Video eliminato.")

# --- INTERFACCIA ---
st.title("🎬 Video Archive")

# Sidebar per Login Amministratore
with st.sidebar:
    st.header("Area Riservata")
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login Admin"):
            if user == ADMIN_USER and pwd == ADMIN_PASS:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Credenziali errate")
    else:
        st.write("Sei loggato come **Admin**")
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

# --- LOGICA VISUALIZZAZIONE ---
videos = get_video_list()

if st.session_state.admin_logged_in:
    st.subheader("🛠️ Gestione Amministratore")
    
    # Upload
    uploaded_file = st.file_uploader("Carica un nuovo video", type=['mp4', 'mov'])
    if uploaded_file is not None:
        if st.button("Conferma Caricamento"):
            upload_video(uploaded_file)
            st.rerun()
    
    st.divider()
    
    # Lista con opzione elimina
    for v in videos:
        col1, col2 = st.columns([3, 1])
        col1.write(v.name)
        if col2.button("Elimina", key=v.sha):
            delete_video(v.path, v.sha)
            st.rerun()

else:
    # Vista Utente Semplice (Autorizzato da Streamlit Cloud)
    st.subheader("📺 I tuoi Video")
    if not videos:
        st.info("Nessun video disponibile al momento.")
    else:
        selected_video_name = st.selectbox("Scegli un video da guardare", [v.name for v in videos])
        
        # Trova l'oggetto file corrispondente
        selected_video = next(v for v in videos if v.name == selected_video_name)
        
        # Usiamo il link "download_url" di GitHub che è un link diretto temporaneo
        st.video(selected_video.download_url)
        st.caption(f"Stai guardando: {selected_video_name}")
