import hashlib
import hmac
import html
import io
import json
import logging
import random
import re
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import boto3
import streamlit as st
import xlsxwriter
from botocore.config import Config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# -----------------------------------------------------------------------------
# CONFIGURAZIONE GENERALE
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Philips Spectral CT Webinar",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OTP_SENDER_EMAIL = "docterrani@gmail.com"
OTP_TTL_MINUTES = 10
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ROME_TZ = ZoneInfo("Europe/Rome")


# -----------------------------------------------------------------------------
# STILE
# -----------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: Inter, Arial, sans-serif;
    }

    .stApp {
        background: linear-gradient(155deg, #f3f8fd 0%, #ffffff 48%, #edf7fc 100%);
        color: #12324a;
    }

    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }

    .block-container {
        max-width: 1240px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    .brandbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 1rem 1.25rem;
        margin-bottom: 1.4rem;
        color: white;
        background: linear-gradient(115deg, #073b74, #0b5ed7 68%, #00aeef);
        border-radius: 18px;
        box-shadow: 0 14px 40px rgba(7, 59, 116, .18);
    }

    .wordmark {
        font-weight: 800;
        letter-spacing: .16em;
        font-size: 1.3rem;
    }

    .brandtitle {
        opacity: .94;
        font-weight: 500;
        text-align: right;
    }

    .hero {
        background: white;
        border: 1px solid #dbeaf4;
        border-radius: 18px;
        padding: 1.5rem;
        box-shadow: 0 10px 35px rgba(17, 65, 96, .08);
        margin-bottom: 1rem;
    }

    .eyebrow {
        color: #0b5ed7;
        font-size: .77rem;
        font-weight: 700;
        letter-spacing: .11em;
        text-transform: uppercase;
    }

    .hero h1 {
        color: #073b74;
        font-size: clamp(1.8rem, 4vw, 3rem);
        line-height: 1.08;
        margin: .35rem 0 .7rem;
    }

    .muted { color: #587185; }

    .video-copy {
        min-height: 96px;
        padding: .2rem .15rem .8rem;
    }

    .video-copy h3 {
        color: #073b74;
        margin-bottom: .35rem;
    }

    div[data-testid="stForm"] {
        background: #fff;
        border: 1px solid #dbeaf4;
        border-radius: 16px;
        padding: 1rem;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        border-radius: 10px;
        border: 1px solid #0b5ed7;
        font-weight: 650;
        min-height: 2.7rem;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: #0b5ed7;
        color: white;
    }

    .stTextInput input,
    .stTextArea textarea {
        background: #fff;
        color: #12324a;
        border-radius: 10px;
    }

    [data-testid="stVideo"] {
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(7, 59, 116, .12);
    }

    @media (max-width: 700px) {
        .block-container { padding: 1rem .8rem 2rem; }
        .brandbar {
            align-items: flex-start;
            flex-direction: column;
        }
        .brandtitle { text-align: left; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# FUNZIONI DI UTILITÀ
# -----------------------------------------------------------------------------

def secret(name, default=None):
    """Legge un Secret Streamlit al livello principale."""
    return st.secrets.get(name, default)


def now_utc():
    return datetime.now(timezone.utc)


def normalize_email(value):
    return (value or "").strip().lower()


def valid_email(value):
    return bool(EMAIL_RE.match(normalize_email(value)))


def brand_header():
    st.markdown(
        '<div class="brandbar">'
        '<div class="wordmark">PHILIPS</div>'
        '<div class="brandtitle">Spectral CT · Webinar professionali</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def logout():
    st.session_state.clear()
    st.rerun()


# -----------------------------------------------------------------------------
# CLOUDFLARE R2
# -----------------------------------------------------------------------------

@st.cache_resource
def get_s3():
    required = ["R2_ENDPOINT", "R2_ACCESS_KEY", "R2_SECRET_KEY", "BUCKET_NAME"]
    missing = [name for name in required if not secret(name)]
    if missing:
        raise RuntimeError(f"Secrets Cloudflare mancanti: {', '.join(missing)}")

    return boto3.client(
        "s3",
        endpoint_url=secret("R2_ENDPOINT"),
        aws_access_key_id=secret("R2_ACCESS_KEY"),
        aws_secret_access_key=secret("R2_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


try:
    s3 = get_s3()
    BUCKET = secret("BUCKET_NAME")
except Exception as exc:
    st.error(f"Configurazione Cloudflare R2 non valida: {exc}")
    st.stop()


def load_json(key, default):
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception as exc:
        message = str(exc)
        if "NoSuchKey" in message or "404" in message:
            return default
        logger.exception("Errore durante la lettura di %s", key)
        st.error(f"Impossibile leggere {key}.")
        return default


def save_json(key, data):
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


# -----------------------------------------------------------------------------
# ACCOUNT E RICHIESTE DI ACCESSO
# -----------------------------------------------------------------------------

def authorized_accounts():
    initial = secret("AUTHORIZED_EMAILS", [])
    seeded = {normalize_email(email) for email in initial if valid_email(email)}

    stored = load_json("authorized_accounts.json", [])
    if isinstance(stored, dict):
        stored = stored.get("emails", [])

    dynamic = {normalize_email(email) for email in stored if valid_email(email)}
    return seeded | dynamic


def save_authorized_accounts(accounts):
    clean = sorted({normalize_email(email) for email in accounts if valid_email(email)})
    save_json("authorized_accounts.json", clean)


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

    requests.append(
        {
            "email": email,
            "requested_at": now_utc().isoformat(),
            "status": "pending",
        }
    )
    save_json("richieste_accesso.json", requests)
    return True


def accept_access_request(email):
    email = normalize_email(email)

    accounts = authorized_accounts()
    accounts.add(email)
    save_authorized_accounts(accounts)

    remaining = [
        request
        for request in access_requests()
        if normalize_email(request.get("email")) != email
    ]
    save_json("richieste_accesso.json", remaining)


# -----------------------------------------------------------------------------
# INVIO E VERIFICA OTP CON GMAIL
# -----------------------------------------------------------------------------

def send_otp(target_email, code):
    sender_name = secret("OTP_SENDER_NAME", "Philips Spectral CT Webinar")
    username = secret("SMTP_USERNAME", OTP_SENDER_EMAIL)
    password = secret("SMTP_PASSWORD")
    host = secret("SMTP_HOST", "smtp.gmail.com")
    port = int(secret("SMTP_PORT", 465))
    use_ssl = bool(secret("SMTP_USE_SSL", True))
    use_starttls = bool(secret("SMTP_USE_STARTTLS", False))

    if not password:
        raise RuntimeError("Il Secret SMTP_PASSWORD non è configurato.")

    message = EmailMessage()
    message["Subject"] = "Il tuo codice di accesso Philips"
    message["From"] = f"{sender_name} <{OTP_SENDER_EMAIL}>"
    message["To"] = target_email
    message.set_content(
        f"Il tuo codice di accesso è: {code}\n\n"
        f"Il codice scade tra {OTP_TTL_MINUTES} minuti.\n"
        "Se non hai richiesto tu il codice, ignora questa email."
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


# -----------------------------------------------------------------------------
# LOGIN AMMINISTRATORE
# -----------------------------------------------------------------------------

def admin_password_is_valid(value):
    """Confronta la password inserita con ADMIN_PASSWORD nei Secrets."""
    expected = str(secret("ADMIN_PASSWORD", "")).strip()
    entered = str(value or "").strip()

    if not expected:
        st.error(
            "Il Secret ADMIN_PASSWORD non è configurato oppure non si trova "
            "al livello principale dei Secrets Streamlit."
        )
        return False

    return hmac.compare_digest(entered, expected)


# -----------------------------------------------------------------------------
# REGISTRO ACCESSI ED ESPORTAZIONI ADMIN
# -----------------------------------------------------------------------------

def record_access(identity, role):
    """Registra ogni login riuscito come evento indipendente su Cloudflare R2."""
    event_time_utc = now_utc()
    event_time_local = event_time_utc.astimezone(ROME_TZ)
    event_id = uuid.uuid4().hex
    key = (
        f"access_logs/{event_time_local:%Y/%m/%d}/"
        f"{event_time_local:%H%M%S_%f}_{event_id}.json"
    )
    event = {
        "event_id": event_id,
        "user": normalize_email(identity) if role == "user" else str(identity).strip(),
        "role": role,
        "accessed_at_utc": event_time_utc.isoformat(),
        "accessed_at_local": event_time_local.isoformat(),
        "timezone": "Europe/Rome",
    }
    save_json(key, event)


def list_access_log_keys():
    keys = []
    continuation_token = None

    while True:
        params = {"Bucket": BUCKET, "Prefix": "access_logs/"}
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**params)
        keys.extend(
            item["Key"]
            for item in response.get("Contents", [])
            if item["Key"].lower().endswith(".json")
        )

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")

    return keys


def load_access_logs(start_date, end_date):
    records = []

    for key in list_access_log_keys():
        # La data è inclusa nel percorso: evita di scaricare eventi fuori periodo.
        parts = key.split("/")
        if len(parts) >= 5:
            try:
                key_date = datetime(
                    int(parts[1]), int(parts[2]), int(parts[3])
                ).date()
                if key_date < start_date or key_date > end_date:
                    continue
            except (TypeError, ValueError):
                pass

        record = load_json(key, None)
        if not isinstance(record, dict):
            continue

        try:
            local_dt = datetime.fromisoformat(record["accessed_at_local"])
        except (KeyError, TypeError, ValueError):
            continue

        if start_date <= local_dt.date() <= end_date:
            record["_local_dt"] = local_dt
            records.append(record)

    return sorted(records, key=lambda item: item["_local_dt"], reverse=True)


def build_access_excel(records, start_date, end_date):
    output = io.BytesIO()

    with xlsxwriter.Workbook(output, {"in_memory": True}) as workbook:
        worksheet = workbook.add_worksheet("Registro accessi")
        worksheet.hide_gridlines(2)
        worksheet.freeze_panes(4, 0)

        title_format = workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": "#FFFFFF",
                "bg_color": "#073B74",
                "align": "center",
                "valign": "vcenter",
            }
        )
        subtitle_format = workbook.add_format(
            {
                "font_size": 10,
                "font_color": "#587185",
                "align": "center",
            }
        )
        header_format = workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#0B5ED7",
                "align": "center",
                "valign": "vcenter",
                "border": 0,
            }
        )
        date_format = workbook.add_format(
            {"num_format": "dd/mm/yyyy hh:mm:ss", "font_color": "#12324A"}
        )
        text_format = workbook.add_format({"font_color": "#12324A"})
        role_format = workbook.add_format(
            {"font_color": "#073B74", "align": "center"}
        )

        worksheet.set_row(0, 28)
        worksheet.merge_range("A1:C1", "PHILIPS - REGISTRO ACCESSI WEBINAR", title_format)
        worksheet.merge_range(
            "A2:C2",
            f"Periodo: {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} | Totale accessi: {len(records)}",
            subtitle_format,
        )
        worksheet.write_row(3, 0, ["Data e ora", "Utente", "Ruolo"], header_format)

        for row_index, record in enumerate(reversed(records), start=4):
            local_dt = record["_local_dt"].replace(tzinfo=None)
            worksheet.write_datetime(row_index, 0, local_dt, date_format)
            worksheet.write(row_index, 1, record.get("user", ""), text_format)
            role_label = "Amministratore" if record.get("role") == "admin" else "Utente"
            worksheet.write(row_index, 2, role_label, role_format)

        last_row = max(4, len(records) + 3)
        worksheet.autofilter(3, 0, last_row, 2)
        worksheet.set_column("A:A", 22)
        worksheet.set_column("B:B", 42)
        worksheet.set_column("C:C", 18)
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.35, 0.35, 0.55, 0.55)

    output.seek(0)
    return output.getvalue()


def _pdf_page_number(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#587185"))
    canvas.drawRightString(
        landscape(A4)[0] - 14 * mm,
        8 * mm,
        f"Pagina {document.page}",
    )
    canvas.restoreState()


def build_access_pdf(records, start_date, end_date):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=14 * mm,
        title="Registro accessi webinar Philips",
        author="Philips Spectral CT Webinar",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PhilipsTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#073B74"),
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )
    info_style = ParagraphStyle(
        "PhilipsInfo",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#587185"),
        alignment=TA_CENTER,
    )

    story = [
        Paragraph("PHILIPS - Registro accessi webinar", title_style),
        Paragraph(
            f"Periodo: {start_date:%d/%m/%Y} - {end_date:%d/%m/%Y} | "
            f"Totale accessi: {len(records)}",
            info_style,
        ),
        Spacer(1, 6 * mm),
    ]

    table_data = [["Data e ora", "Utente", "Ruolo"]]
    for record in reversed(records):
        role_label = "Amministratore" if record.get("role") == "admin" else "Utente"
        table_data.append(
            [
                record["_local_dt"].strftime("%d/%m/%Y %H:%M:%S"),
                str(record.get("user", "")),
                role_label,
            ]
        )

    if len(table_data) == 1:
        table_data.append(["-", "Nessun accesso nel periodo selezionato", "-"])

    table = Table(
        table_data,
        colWidths=[48 * mm, 150 * mm, 42 * mm],
        repeatRows=1,
        hAlign="CENTER",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F8FD")]),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#073B74")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#DCEAF4")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    document.build(
        story,
        onFirstPage=_pdf_page_number,
        onLaterPages=_pdf_page_number,
    )
    output.seek(0)
    return output.getvalue()


# -----------------------------------------------------------------------------
# VIDEO E METADATI
# -----------------------------------------------------------------------------

def list_videos():
    response = s3.list_objects_v2(Bucket=BUCKET)
    return sorted(
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
    )


def video_metadata():
    data = load_json("video_metadata.json", {})
    return data if isinstance(data, dict) else {}


def default_title(video_key):
    filename = video_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return filename.replace("_", " ").replace("-", " ").strip().title()


# -----------------------------------------------------------------------------
# PROSSIMI EVENTI
# -----------------------------------------------------------------------------

def upcoming_events():
    data = load_json("upcoming_events.json", [])
    if not isinstance(data, list):
        return []
    return sorted(
        data,
        key=lambda item: (
            item.get("event_date", "9999-12-31"),
            item.get("created_at", ""),
        ),
    )


def save_upcoming_events(events):
    save_json("upcoming_events.json", events)


def visible_upcoming_events():
    today = datetime.now(ROME_TZ).date()
    visible = []

    for event in upcoming_events():
        try:
            event_date = datetime.fromisoformat(event.get("event_date", "")).date()
        except (TypeError, ValueError):
            event_date = today

        if event_date >= today:
            visible.append(event)

    return visible


def event_image_url(event):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": event["image_key"]},
        ExpiresIn=3600,
    )


def render_upcoming_events():
    events = visible_upcoming_events()
    st.divider()
    st.subheader("Prossimi eventi")

    if not events:
        st.info("Non ci sono eventi programmati al momento.")
        return

    columns = st.columns(3)

    for index, event in enumerate(events):
        with columns[index % 3]:
            try:
                st.image(event_image_url(event), use_container_width=True)
            except Exception:
                logger.exception("Impossibile caricare la locandina evento")
                st.warning("Locandina temporaneamente non disponibile.")

            title = event.get("title", "").strip()
            if title:
                st.markdown(f"#### {html.escape(title)}")

            event_date = event.get("event_date", "")
            try:
                formatted_date = datetime.fromisoformat(event_date).strftime("%d/%m/%Y")
                st.caption(f"Data evento: {formatted_date}")
            except (TypeError, ValueError):
                pass

            description = event.get("description", "").strip()
            if description:
                st.write(description)


# -----------------------------------------------------------------------------
# STATO DELLA SESSIONE
# -----------------------------------------------------------------------------

for key, value in {
    "screen": "login",
    "role": None,
    "identity": None,
}.items():
    st.session_state.setdefault(key, value)


# -----------------------------------------------------------------------------
# INTERFACCIA
# -----------------------------------------------------------------------------

brand_header()


if st.session_state.screen == "login":
    _, center, _ = st.columns([1, 1.35, 1])

    with center:
        st.markdown(
            '<div class="hero">'
            '<div class="eyebrow">Accesso riservato</div>'
            '<h1>Formazione Spectral CT</h1>'
            '<p class="muted">Inserisci la tua email. Gli utenti abilitati '
            'riceveranno un codice OTP.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        with st.form("identity_form"):
            identity = st.text_input(
                "Email o nome amministratore",
                placeholder="nome.cognome@azienda.com",
            )
            submitted = st.form_submit_button(
                "Continua",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            admin_username = str(secret("ADMIN_USERNAME", "Admin")).strip()

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
                        logger.exception("Invio OTP non riuscito")
                        st.error(
                            "Non è stato possibile inviare il codice. "
                            "Controlla SMTP_USERNAME, SMTP_PASSWORD e la password per le app Google."
                        )
                else:
                    created = enqueue_access_request(email)
                    if created:
                        st.success(
                            "Account non ancora abilitato: la richiesta è stata "
                            "inviata all’amministratore."
                        )
                    else:
                        st.info(
                            "La richiesta per questo account è già in attesa di approvazione."
                        )

    render_upcoming_events()


elif st.session_state.screen in {"verify_admin", "verify_otp"}:
    _, center, _ = st.columns([1, 1.2, 1])

    with center:
        is_admin = st.session_state.screen == "verify_admin"
        st.subheader("Verifica accesso")
        st.caption(f"Accesso per {st.session_state.identity}")

        with st.form("verification_form"):
            value = st.text_input(
                "Password" if is_admin else "Codice OTP",
                type="password",
                max_chars=64,
            )
            confirm = st.form_submit_button(
                "Accedi",
                type="primary",
                use_container_width=True,
            )

        if confirm:
            valid = admin_password_is_valid(value) if is_admin else otp_is_valid(value)

            if valid:
                role = "admin" if is_admin else "user"
                try:
                    record_access(st.session_state.identity, role)
                except Exception:
                    logger.exception("Registrazione accesso non riuscita")
                st.session_state.role = role
                st.session_state.screen = "portal"
                st.rerun()
            else:
                st.error(
                    "Password amministratore non valida."
                    if is_admin
                    else "Codice OTP non valido o scaduto."
                )

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

    render_upcoming_events()

    try:
        videos = list_videos()
        metadata = video_metadata()

        if not videos:
            st.info("Non sono ancora disponibili webinar.")
        else:
            st.subheader("Webinar disponibili")
            columns = st.columns(2)

            for index, video_key in enumerate(videos):
                item = metadata.get(video_key, {})
                title = item.get("title") or default_title(video_key)
                description = (
                    item.get("description")
                    or "Approfondimento video riservato agli utenti autorizzati."
                )

                safe_title = html.escape(title)
                safe_description = html.escape(description)

                video_url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": BUCKET, "Key": video_key},
                    ExpiresIn=3600,
                )

                with columns[index % 2]:
                    st.markdown(
                        f'<div class="video-copy"><h3>{safe_title}</h3>'
                        f'<p class="muted">{safe_description}</p></div>',
                        unsafe_allow_html=True,
                    )
                    st.video(video_url)

    except Exception as exc:
        logger.exception("Errore caricamento webinar")
        st.error(f"Impossibile caricare i webinar: {exc}")
        videos = []
        metadata = {}

    if st.session_state.role == "user":
        st.divider()
        st.subheader("La tua opinione")

        with st.form("feedback_form", clear_on_submit=True):
            rating = st.selectbox(
                "Valutazione",
                ["Eccellente", "Ottimo", "Buono", "Sufficiente"],
            )
            comments = st.text_area("Commenti o richieste")

            if st.form_submit_button("Invia feedback", type="primary"):
                feedback = load_json("feedback_webinar.json", [])
                feedback.append(
                    {
                        "user": st.session_state.identity,
                        "rating": rating,
                        "comments": comments.strip(),
                        "created_at": now_utc().isoformat(),
                    }
                )
                save_json("feedback_webinar.json", feedback)
                st.success("Feedback registrato. Grazie.")

    if st.session_state.role == "admin":
        st.divider()
        st.header("Pannello amministratore")

        requests_tab, access_tab, events_tab, video_tab, upload_tab, feedback_tab = st.tabs(
            [
                "Richieste account",
                "Registro accessi",
                "Prossimi eventi",
                "Descrizioni video",
                "Carica video",
                "Feedback",
            ]
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
                        st.caption(
                            request.get("requested_at")
                            or request.get("date", "")
                        )

                    with action_col:
                        button_key = hashlib.sha1(email.encode()).hexdigest()
                        if st.button(
                            "Accetta account",
                            key=f"accept_{button_key}",
                            type="primary",
                        ):
                            accept_access_request(email)
                            st.success(f"{email} è ora abilitato.")
                            st.rerun()

        with access_tab:
            st.subheader("Registro degli accessi")
            st.caption(
                "Sono registrati esclusivamente i login riusciti. "
                "Date e orari sono visualizzati nel fuso Europe/Rome."
            )

            today = datetime.now(ROME_TZ).date()
            default_start = today.replace(day=1)
            start_col, end_col = st.columns(2)

            with start_col:
                start_date = st.date_input(
                    "Dal",
                    value=default_start,
                    key="access_start_date",
                )
            with end_col:
                end_date = st.date_input(
                    "Al",
                    value=today,
                    key="access_end_date",
                )

            if start_date > end_date:
                st.error("La data iniziale non può essere successiva alla data finale.")
            else:
                with st.spinner("Caricamento del registro…"):
                    access_records = load_access_logs(start_date, end_date)

                total_accesses = len(access_records)
                unique_users = len(
                    {record.get("user", "") for record in access_records}
                )
                admin_accesses = sum(
                    1 for record in access_records if record.get("role") == "admin"
                )

                metric_1, metric_2, metric_3 = st.columns(3)
                metric_1.metric("Accessi", total_accesses)
                metric_2.metric("Utenti unici", unique_users)
                metric_3.metric("Accessi admin", admin_accesses)

                display_rows = [
                    {
                        "Data e ora": record["_local_dt"].strftime("%d/%m/%Y %H:%M:%S"),
                        "Utente": record.get("user", ""),
                        "Ruolo": (
                            "Amministratore"
                            if record.get("role") == "admin"
                            else "Utente"
                        ),
                    }
                    for record in access_records
                ]

                if display_rows:
                    st.dataframe(
                        display_rows,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("Nessun accesso nel periodo selezionato.")

                excel_data = build_access_excel(
                    access_records,
                    start_date,
                    end_date,
                )
                pdf_data = build_access_pdf(
                    access_records,
                    start_date,
                    end_date,
                )

                excel_col, pdf_col = st.columns(2)
                filename_period = f"{start_date:%Y%m%d}_{end_date:%Y%m%d}"

                with excel_col:
                    st.download_button(
                        "Scarica Excel",
                        data=excel_data,
                        file_name=f"registro_accessi_{filename_period}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

                with pdf_col:
                    st.download_button(
                        "Scarica PDF",
                        data=pdf_data,
                        file_name=f"registro_accessi_{filename_period}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

        with events_tab:
            st.subheader("Gestione prossimi eventi")
            st.caption(
                "Gli eventi vengono mostrati nel login e nella pagina webinar. "
                "Dopo la data indicata non saranno più visibili agli utenti."
            )

            with st.form("event_upload_form", clear_on_submit=True):
                event_title = st.text_input("Titolo evento")
                event_date = st.date_input(
                    "Data evento",
                    value=datetime.now(ROME_TZ).date(),
                    key="new_event_date",
                )
                event_description = st.text_area(
                    "Descrizione breve",
                    height=90,
                )
                event_image = st.file_uploader(
                    "Locandina evento",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="event_image_uploader",
                )
                save_event = st.form_submit_button(
                    "Pubblica evento",
                    type="primary",
                    use_container_width=True,
                )

            if save_event:
                if event_image is None:
                    st.error("Seleziona un’immagine per la locandina.")
                else:
                    extension = event_image.name.rsplit(".", 1)[-1].lower()
                    event_id = uuid.uuid4().hex
                    image_key = f"event_images/{event_id}.{extension}"

                    try:
                        s3.upload_fileobj(
                            event_image,
                            BUCKET,
                            image_key,
                            ExtraArgs={
                                "ContentType": event_image.type or "application/octet-stream"
                            },
                        )

                        events = upcoming_events()
                        events.append(
                            {
                                "event_id": event_id,
                                "title": event_title.strip(),
                                "event_date": event_date.isoformat(),
                                "description": event_description.strip(),
                                "image_key": image_key,
                                "created_at": now_utc().isoformat(),
                                "created_by": st.session_state.identity,
                            }
                        )
                        save_upcoming_events(events)
                        st.success("Evento pubblicato correttamente.")
                        st.rerun()
                    except Exception as exc:
                        logger.exception("Pubblicazione evento non riuscita")
                        st.error(f"Impossibile pubblicare l’evento: {exc}")

            all_events = upcoming_events()
            if not all_events:
                st.info("Non sono ancora stati caricati eventi.")

            for event in all_events:
                event_id = event.get("event_id", uuid.uuid4().hex)
                with st.container(border=True):
                    preview_col, detail_col, delete_col = st.columns([1.2, 3, 1])

                    with preview_col:
                        try:
                            st.image(event_image_url(event), use_container_width=True)
                        except Exception:
                            st.caption("Anteprima non disponibile")

                    with detail_col:
                        st.markdown(
                            f"**{event.get('title') or 'Evento senza titolo'}**"
                        )
                        try:
                            formatted_date = datetime.fromisoformat(
                                event.get("event_date", "")
                            ).strftime("%d/%m/%Y")
                            st.caption(f"Data evento: {formatted_date}")
                        except (TypeError, ValueError):
                            pass
                        if event.get("description"):
                            st.write(event["description"])

                    with delete_col:
                        if st.button(
                            "Elimina",
                            key=f"delete_event_{event_id}",
                            type="secondary",
                            use_container_width=True,
                        ):
                            try:
                                if event.get("image_key"):
                                    s3.delete_object(
                                        Bucket=BUCKET,
                                        Key=event["image_key"],
                                    )
                                remaining = [
                                    item
                                    for item in all_events
                                    if item.get("event_id") != event.get("event_id")
                                ]
                                save_upcoming_events(remaining)
                                st.success("Evento eliminato.")
                                st.rerun()
                            except Exception as exc:
                                logger.exception("Eliminazione evento non riuscita")
                                st.error(f"Impossibile eliminare l’evento: {exc}")

        with video_tab:
            if not videos:
                st.info("Carica prima almeno un video.")

            for video_key in videos:
                current = metadata.get(video_key, {})
                form_key = hashlib.sha1(video_key.encode()).hexdigest()

                with st.expander(current.get("title") or default_title(video_key)):
                    with st.form(f"metadata_{form_key}"):
                        new_title = st.text_input(
                            "Titolo",
                            value=current.get("title") or default_title(video_key),
                        )
                        new_description = st.text_area(
                            "Descrizione",
                            value=current.get("description", ""),
                            height=120,
                        )

                        if st.form_submit_button(
                            "Salva descrizione",
                            type="primary",
                        ):
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
            upload = st.file_uploader(
                "Video",
                type=["mp4", "mov", "m4v", "webm"],
            )

            if upload and st.button(
                "Carica su Cloudflare R2",
                type="primary",
            ):
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
                    rating = item.get("rating") or item.get("valutazione", "")
                    user = item.get("user", "")
                    comments = item.get("comments") or item.get("richieste", "")
                    created_at = item.get("created_at") or item.get("data", "")

                    st.markdown(f"**{rating}** · {user}")
                    st.write(comments)
                    st.caption(created_at)
