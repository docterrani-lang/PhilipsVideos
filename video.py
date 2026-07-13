import hashlib
import hmac
import html
import json
import random
import re
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import boto3
import streamlit as st
from botocore.config import Config


st.set_page_config(
    page_title="Philips Spectral CT Webinar",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PHILIPS_BLUE = "#0B5ED7"
PHILIPS_DARK = "#073B74"
PHILIPS_CYAN = "#00AEEF"
OTP_TTL_MINUTES = 10
OTP_SENDER_EMAIL = "simone.terrani@philips.com"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: Inter, Arial, sans-serif; }
    .stApp { background: linear-gradient(155deg, #f3f8fd 0%, #ffffff 48%, #edf7fc 100%); color: #12324a; }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { max-width: 1240px; padding-top: 1.5rem; padding-bottom: 3rem; }
    .brandbar {
        display:flex; align-items:center; justify-content:space-between; gap:1rem;
        padding:1rem 1.25rem; margin-bottom:1.4rem; color:white;
        background:linear-gradient(115deg,#073b74,#0b5ed7 68%,#00aeef);
        border-radius:18px; box-shadow:0 14px 40px rgba(7,59,116,.18);
    }
    .wordmark { font-weight:800; letter-spacing:.16em; font-size:1.3rem; }
    .brandtitle { opacity:.94; font-weight:500; text-align:right; }
    .hero { background:white; border:1px solid #dbeaf4; border-radius:18px; padding:1.5rem;
            box-shadow:0 10px 35px rgba(17,65,96,.08); margin-bottom:1rem; }
    .eyebrow { color:#0b5ed7; font-size:.77rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }
    .hero h1 { color:#073b74; font-size:clamp(1.8rem,4vw,3rem); line-height:1.08; margin:.35rem 0 .7rem; }
    .muted { color:#587185; }
    .video-copy { min-height:96px; padding:.2rem .15rem .8rem; }
    .video-copy h3 { color:#073b74; margin-bottom:.35rem; }
    .admin-card { background:#fff; border:1px solid #dbeaf4; border-radius:16px; padding:1rem 1.1rem; margin:.5rem 0; }
    div[data-testid="stForm"] { background:#fff; border:1px solid #dbeaf4; border-radius:16px; padding:1rem; }
    .stButton > button, .stFormSubmitButton > button {
        border-radius:10px; border:1px solid #0b5ed7; font-weight:650; min-height:2.7rem;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background:#0b5ed7; color:white;
    }
    .stTextInput input, .stTextArea textarea { background:#fff; color:#12324a; border-radius:10px; }
    [data-testid="stVideo"] { border-radius:14px; overflow:hidden; box-shadow:0 8px 24px rgba(7,59,116,.12); }
    @media (max-width: 700px) {
        .block-container { padding:1rem .8rem 2rem; }
        .brandbar { align-items:flex-start; flex-direction:column; }
        .brandtitle { text-align:left; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def now_utc():
    return datetime.now(timezone.utc)


def normalize_email(value):
    return (value or "").strip().lower()


def valid_email(value):
    return bool(EMAIL_RE.match(normalize_email(value)))


def secret(name, default=None):
    return st.secrets.get(name, default)


@st.cache_resource
def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=secret("R2_ENDPOINT"),
        aws_access_key_id=secret("R2_ACCESS_KEY"),
        aws_secret_access_key=secret("R2_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


s3 = get_s3()
BUCKET = secret("BUCKET_NAME")


def load_json(key, default):
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return default
    except Exception as exc:
        if "NoSuchKey" in str(exc) or "404" in str(exc):
            return default
        st.error(f"Impossibile leggere {key}: {exc}")
        return default


def save_json(key, data):
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def authorized_accounts():
    seeded = {normalize_email(x) for x in secret("AUTHORIZED_EMAILS", []) if valid_email(x)}
    stored = load_json("authorized_accounts.json", [])
    if isinstance(stored, dict):
        stored = stored.get("emails", [])
    return seeded | {normalize_email(x) for x in stored if valid_email(x)}


def save_authorized_accounts(accounts):
    save_json("authorized_accounts.json", sorted({normalize_email(x) for x in accounts if valid_email(x)}))


def access_requests():
    data = load_json("richieste_accesso.json", [])
    return data if isinstance(data, list) else []


def enqueue_access_request(email):
    email = normalize_email(email)
    requests = access_requests()
    if email in authorized_accounts():
        return False
    if any(normalize_email(item.get("email")) == email for item in requests):
        return False
    requests.append({"email": email, "requested_at": now_utc().isoformat(), "status": "pending"})
    save_json("richieste_accesso.json", requests)
    return True


def accept_access_request(email):
    email = normalize_email(email)
    accounts = authorized_accounts()
    accounts.add(email)
    save_authorized_accounts(accounts)
    remaining = [r for r in access_requests() if normalize_email(r.get("email")) != email]
    save_json("richieste_accesso.json", remaining)


def send_otp(target_email, code):
    sender = OTP_SENDER_EMAIL
    sender_name = secret("OTP_SENDER_NAME", "Philips Spectral CT Webinar")
    username = secret("SMTP_USERNAME", sender)
    password = secret("SMTP_PASSWORD")
    host = secret("SMTP_HOST", "smtp.office365.com")
    port = int(secret("SMTP_PORT", 587))
    use_ssl = bool(secret("SMTP_USE_SSL", False))
    use_starttls = bool(secret("SMTP_USE_STARTTLS", not use_ssl))

    message = EmailMessage()
    message["Subject"] = "Il tuo codice di accesso Philips"
    message["From"] = f"{sender_name} <{sender}>"
    message["To"] = target_email
    message.set_content(
        f"Il tuo codice di accesso è {code}.\n\n"
        f"Scade tra {OTP_TTL_MINUTES} minuti. Se non hai richiesto tu il codice, ignora questa email."
    )
    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            if use_starttls:
                server.starttls(context=context)
                server.ehlo()
            server.login(username, password)
            server.send_message(message)


def issue_otp(email):
    code = f"{random.SystemRandom().randint(0, 999999):06d}"
    send_otp(email, code)
    st.session_state.otp_digest = hashlib.sha256(code.encode()).hexdigest()
    st.session_state.otp_expires = now_utc() + timedelta(minutes=OTP_TTL_MINUTES)
    st.session_state.otp_attempts = 0


def otp_is_valid(value):
    if st.session_state.get("otp_attempts", 0) >= 5:
        return False
    st.session_state.otp_attempts = st.session_state.get("otp_attempts", 0) + 1
    expires = st.session_state.get("otp_expires")
    if not expires or now_utc() > expires:
        return False
    digest = hashlib.sha256((value or "").strip().encode()).hexdigest()
    return hmac.compare_digest(digest, st.session_state.get("otp_digest", ""))


def admin_password_is_valid(value):
    expected_hash = secret("ADMIN_PASSWORD_HASH")
    if expected_hash:
        actual = hashlib.sha256((value or "").encode()).hexdigest()
        return hmac.compare_digest(actual, expected_hash)
    expected = str(secret("ADMIN_PASSWORD", ""))
    return bool(expected) and hmac.compare_digest(value or "", expected)


def list_videos():
    response = s3.list_objects_v2(Bucket=BUCKET)
    return sorted(
        obj["Key"] for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
    )


def video_metadata():
    data = load_json("video_metadata.json", {})
    return data if isinstance(data, dict) else {}


def default_title(video_key):
    return video_key.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip().title()


def brand_header():
    st.markdown(
        '<div class="brandbar"><div class="wordmark">PHILIPS</div>'
        '<div class="brandtitle">Spectral CT · Webinar professionali</div></div>',
        unsafe_allow_html=True,
    )


def logout():
    st.session_state.clear()
    st.rerun()


for key, value in {"screen": "login", "role": None, "identity": None}.items():
    st.session_state.setdefault(key, value)

brand_header()

if st.session_state.screen == "login":
    left, center, right = st.columns([1, 1.35, 1])
    with center:
        st.markdown(
            '<div class="hero"><div class="eyebrow">Accesso riservato</div>'
            '<h1>Formazione Spectral CT</h1><p class="muted">Inserisci la tua email aziendale. '
            'Gli utenti abilitati riceveranno un codice OTP.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("identity_form"):
            identity = st.text_input("Email o nome amministratore", placeholder="nome.cognome@azienda.com")
            submitted = st.form_submit_button("Continua", type="primary", use_container_width=True)
        if submitted:
            admin_username = str(secret("ADMIN_USERNAME", "Admin"))
            if hmac.compare_digest(identity.strip(), admin_username):
                st.session_state.identity = identity.strip()
                st.session_state.screen = "verify_admin"
                st.rerun()
            elif not valid_email(identity):
                st.error("Inserisci un indirizzo email valido.")
            else:
                email = normalize_email(identity)
                if email in authorized_accounts():
                    try:
                        issue_otp(email)
                        st.session_state.identity = email
                        st.session_state.screen = "verify_otp"
                        st.rerun()
                    except Exception:
                        st.error("Non è stato possibile inviare il codice. Controlla la configurazione SMTP.")
                else:
                    created = enqueue_access_request(email)
                    if created:
                        st.success("Account non ancora abilitato: la richiesta è stata inviata all’amministratore.")
                    else:
                        st.info("La richiesta per questo account è già in attesa di approvazione.")

elif st.session_state.screen in {"verify_admin", "verify_otp"}:
    left, center, right = st.columns([1, 1.2, 1])
    with center:
        is_admin = st.session_state.screen == "verify_admin"
        st.subheader("Verifica accesso")
        st.caption(f"Accesso per {st.session_state.identity}")
        with st.form("verification_form"):
            value = st.text_input("Password" if is_admin else "Codice OTP", type="password", max_chars=64)
            confirm = st.form_submit_button("Accedi", type="primary", use_container_width=True)
        if confirm:
            valid = admin_password_is_valid(value) if is_admin else otp_is_valid(value)
            if valid:
                st.session_state.role = "admin" if is_admin else "user"
                st.session_state.screen = "portal"
                st.rerun()
            else:
                st.error("Credenziale non valida o codice scaduto.")
        if st.button("Torna indietro", use_container_width=True):
            st.session_state.screen = "login"
            st.rerun()

elif st.session_state.screen == "portal":
    title_col, logout_col = st.columns([5, 1])
    with title_col:
        st.markdown('<div class="eyebrow">Knowledge hub</div>', unsafe_allow_html=True)
        st.title("Webinar Spectral CT")
        st.caption(f"Connesso come {st.session_state.identity}")
    with logout_col:
        if st.button("Esci", use_container_width=True):
            logout()

    try:
        videos = list_videos()
        metadata = video_metadata()
        if not videos:
            st.info("Non sono ancora disponibili webinar.")
        else:
            st.subheader("Webinar disponibili")
            cols = st.columns(2)
            for index, video_key in enumerate(videos):
                item = metadata.get(video_key, {})
                title = item.get("title") or default_title(video_key)
                description = item.get("description") or "Approfondimento video riservato agli utenti autorizzati."
                safe_title = html.escape(title)
                safe_description = html.escape(description)
                url = s3.generate_presigned_url(
                    "get_object", Params={"Bucket": BUCKET, "Key": video_key}, ExpiresIn=3600
                )
                with cols[index % 2]:
                    st.markdown(
                        f'<div class="video-copy"><h3>{safe_title}</h3><p class="muted">{safe_description}</p></div>',
                        unsafe_allow_html=True,
                    )
                    st.video(url)
    except Exception as exc:
        st.error(f"Impossibile caricare i webinar: {exc}")

    if st.session_state.role == "user":
        st.divider()
        st.subheader("La tua opinione")
        with st.form("feedback_form", clear_on_submit=True):
            rating = st.selectbox("Valutazione", ["Eccellente", "Ottimo", "Buono", "Sufficiente"])
            comments = st.text_area("Commenti o richieste")
            if st.form_submit_button("Invia feedback", type="primary"):
                feedback = load_json("feedback_webinar.json", [])
                feedback.append({
                    "user": st.session_state.identity,
                    "rating": rating,
                    "comments": comments.strip(),
                    "created_at": now_utc().isoformat(),
                })
                save_json("feedback_webinar.json", feedback)
                st.success("Feedback registrato. Grazie.")

    if st.session_state.role == "admin":
        st.divider()
        st.header("Pannello amministratore")
        requests_tab, video_tab, upload_tab, feedback_tab = st.tabs(
            ["Richieste account", "Descrizioni video", "Carica video", "Feedback"]
        )

        with requests_tab:
            requests = access_requests()
            if not requests:
                st.info("Non ci sono richieste in attesa.")
            for request in requests:
                email = normalize_email(request.get("email"))
                with st.container(border=True):
                    info_col, action_col = st.columns([4, 1])
                    with info_col:
                        st.markdown(f"**{email}**")
                        st.caption(request.get("requested_at") or request.get("date", ""))
                    with action_col:
                        if st.button("Accetta account", key=f"accept_{hashlib.sha1(email.encode()).hexdigest()}", type="primary"):
                            accept_access_request(email)
                            st.success(f"{email} è ora abilitato.")
                            st.rerun()

        with video_tab:
            if not videos:
                st.info("Carica prima almeno un video.")
            for video_key in videos:
                current = metadata.get(video_key, {})
                with st.expander(current.get("title") or default_title(video_key)):
                    with st.form(f"metadata_{hashlib.sha1(video_key.encode()).hexdigest()}"):
                        new_title = st.text_input("Titolo", value=current.get("title") or default_title(video_key))
                        new_description = st.text_area("Descrizione", value=current.get("description", ""), height=120)
                        if st.form_submit_button("Salva descrizione", type="primary"):
                            metadata[video_key] = {
                                "title": new_title.strip() or default_title(video_key),
                                "description": new_description.strip(),
                                "updated_at": now_utc().isoformat(),
                                "updated_by": st.session_state.identity,
                            }
                            save_json("video_metadata.json", metadata)
                            st.success("Descrizione aggiornata.")
                            st.rerun()

        with upload_tab:
            upload = st.file_uploader("Video", type=["mp4", "mov", "m4v", "webm"])
            if upload and st.button("Carica su Cloudflare R2", type="primary"):
                with st.spinner("Caricamento in corso…"):
                    s3.upload_fileobj(upload, BUCKET, upload.name)
                st.success("Video caricato.")
                st.rerun()

        with feedback_tab:
            feedback = load_json("feedback_webinar.json", [])
            if not feedback:
                st.info("Nessun feedback ricevuto.")
            for item in reversed(feedback[-50:]):
                with st.container(border=True):
                    st.markdown(f"**{item.get('rating') or item.get('valutazione', '')}** · {item.get('user', '')}")
                    st.write(item.get("comments") or item.get("richieste", ""))
                    st.caption(item.get("created_at") or item.get("data", ""))
