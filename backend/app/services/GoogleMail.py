import base64
import html
import re
import time
import unicodedata
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.User import GoogleAccount, User
from app.services import Auth
from app.services.UserCv import get_cv


TOKEN_URL = Auth.TOKEN_URL
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
SEND_URL = f"{GMAIL_API}/messages/send"
REQUEST_TIMEOUT = 20
PUBLIC_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "msn.com", "yahoo.com", "icloud.com", "me.com", "aol.com", "sapo.pt",
}
CV_MIME = {
    "pdf": ("application", "pdf"),
    "docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "odt": ("application", "vnd.oasis.opendocument.text"),
    "rtf": ("application", "rtf"),
    "txt": ("text", "plain"),
    "md": ("text", "markdown"),
    "html": ("text", "html"),
    "htm": ("text", "html"),
    "jpg": ("image", "jpeg"),
    "jpeg": ("image", "jpeg"),
    "png": ("image", "png"),
    "webp": ("image", "webp"),
}


def _cv_mime(filename: str) -> tuple[str, str]:
    return CV_MIME.get(Path(filename).suffix.casefold().lstrip("."), ("application", "octet-stream"))

# Cache em memória dos access tokens (curta duração) por utilizador.
_access_tokens: dict[int, tuple[str, float]] = {}
_mail_read_ok: dict[int, bool] = {}


class GoogleError(Exception):
    pass


def is_configured() -> bool:
    return Auth.is_configured()


def connect(
    db: Session,
    user: User,
    code: str,
    redirect_uri: str | None = None,
    code_verifier: str | None = None,
) -> None:
    try:
        payload = Auth.exchange_code(code, redirect_uri=redirect_uri, code_verifier=code_verifier)
        info = Auth.fetch_userinfo(payload["access_token"])
    except Auth.AuthError as error:
        raise GoogleError(str(error)) from error
    if info["sub"] != user.google_sub:
        raise GoogleError("Liga o Gmail com a mesma conta Google usada no login.")
    if "refresh_token" not in payload:
        raise GoogleError("A Google não devolveu permissão duradoura. Tenta ligar de novo.")

    account = db.get(GoogleAccount, user.id_user)
    if account is None:
        account = GoogleAccount(id_user=user.id_user)
        db.add(account)
    account.email = info["email"]
    account.refresh_token_encrypted = Auth.encrypt(payload["refresh_token"])
    db.commit()
    _access_tokens[user.id_user] = (payload["access_token"], time.time() + payload.get("expires_in", 3600))
    _mail_read_ok.pop(user.id_user, None)


def disconnect(db: Session, user: User) -> None:
    db.query(GoogleAccount).filter(GoogleAccount.id_user == user.id_user).delete()
    db.commit()
    _access_tokens.pop(user.id_user, None)
    _mail_read_ok.pop(user.id_user, None)


def _access_token(account: GoogleAccount) -> str:
    cached = _access_tokens.get(account.id_user)
    if cached and cached[1] - 60 > time.time():
        return cached[0]

    try:
        refresh_token = Auth.decrypt(account.refresh_token_encrypted)
        response = httpx.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except Auth.AuthError as error:
        raise GoogleError(str(error)) from error
    except httpx.HTTPError as error:
        raise GoogleError("Não foi possível contactar a Google.") from error
    if response.status_code != 200:
        raise GoogleError("A Google recusou a autorização. Liga o Gmail de novo.")

    payload = response.json()
    _access_tokens[account.id_user] = (payload["access_token"], time.time() + payload.get("expires_in", 3600))
    return payload["access_token"]


def _can_follow_replies(account: GoogleAccount) -> bool:
    cached = _mail_read_ok.get(account.id_user)
    if cached is not None:
        return cached
    try:
        _gmail_get(account, "/profile")
        return True
    except GoogleError:
        return False


def status(db: Session, user: User) -> dict:
    account = db.get(GoogleAccount, user.id_user)
    return {
        "configured": is_configured(),
        "connected": account is not None,
        "email": account.email if account else None,
        "can_follow_replies": bool(account) and _can_follow_replies(account),
    }


def build_message(to: str, subject: str, body: str, sender: str | None, cv) -> EmailMessage:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    message.set_content(body)

    if cv is not None:
        maintype, subtype = _cv_mime(cv.filename)
        message.add_attachment(cv.content, maintype=maintype, subtype=subtype, filename=cv.filename)
    return message


def send_email(db: Session, user: User, to: str, subject: str, body: str, attach_cv: bool = True) -> str | None:
    if any(char in value for value in (to, subject) for char in "\r\n"):
        raise GoogleError("Destinatário ou assunto inválido.")

    account = db.get(GoogleAccount, user.id_user)
    if account is None:
        raise GoogleError("Liga primeiro a tua conta Gmail.")

    access_token = _access_token(account)
    cv = get_cv(db, user) if attach_cv else None
    message = build_message(to, subject, body, account.email, cv)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        response = httpx.post(
            SEND_URL,
            headers={"Authorization": "Bearer " + access_token},
            json={"raw": raw},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise GoogleError("Não foi possível contactar a Google.") from error
    if response.status_code != 200:
        raise GoogleError("A Google recusou o envio do email.")
    payload = response.json()
    return payload.get("threadId") if isinstance(payload, dict) else None


def _gmail_get(account: GoogleAccount, path: str, params: dict | None = None) -> dict | None:
    try:
        response = httpx.get(
            f"{GMAIL_API}{path}",
            headers={"Authorization": "Bearer " + _access_token(account)},
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise GoogleError("Não foi possível contactar a Google.") from error
    if response.status_code == 404:
        return None
    if response.status_code == 403:
        _mail_read_ok[account.id_user] = False
        raise GoogleError("Liga o Gmail de novo para seguir as respostas.")
    if response.status_code != 200:
        raise GoogleError("A Google recusou a leitura da caixa de correio.")
    payload = response.json()
    if isinstance(payload, dict):
        _mail_read_ok[account.id_user] = True
        return payload
    return None


def _from_address(headers: list | None) -> str:
    for header in headers or []:
        if str(header.get("name") or "").casefold() == "from":
            return parseaddr(str(header.get("value") or ""))[1].casefold()
    return ""


def _reply_query(contact_email: str, sent_at: datetime | None) -> str:
    address = contact_email.strip().casefold()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    query = f"from:{address}" if not domain or domain in PUBLIC_MAIL_DOMAINS else f"(from:{address} OR from:@{domain})"
    return f"{query} after:{int(sent_at.timestamp())}" if sent_at else query


def _message_date(message: dict) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OSError):
        return None


def find_sent_message(account: GoogleAccount, contact_email: str) -> tuple[str, datetime | None] | None:
    """Encontra nos Enviados o último email para o contacto: devolve a conversa e a data de envio."""
    listed = _gmail_get(account, "/messages", {"q": f"in:sent to:{contact_email.strip()}", "maxResults": 1})
    items = (listed or {}).get("messages") or []
    if not items:
        return None
    message = _gmail_get(account, f"/messages/{items[0]['id']}", {"format": "minimal"}) or {}
    return items[0]["threadId"], _message_date(message)


def has_reply(account: GoogleAccount, thread_id: str | None, contact_email: str | None, sent_at: datetime | None) -> bool:
    our_email = (account.email or "").casefold()
    if thread_id:
        thread = _gmail_get(account, f"/threads/{thread_id}", {"format": "metadata", "metadataHeaders": "From"})
        for message in (thread or {}).get("messages") or []:
            sender = _from_address((message.get("payload") or {}).get("headers"))
            if sender and sender != our_email:
                return True
    if not contact_email:
        return False
    listed = _gmail_get(account, "/messages", {"q": _reply_query(contact_email, sent_at), "maxResults": 1})
    return bool((listed or {}).get("messages"))


def _decode_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")


def _walk_parts(payload: dict) -> list[tuple[str, str]]:
    mime = str(payload.get("mimeType") or "").casefold()
    data = (payload.get("body") or {}).get("data")
    found: list[tuple[str, str]] = []
    if data and (mime.startswith("text/plain") or "html" in mime):
        found.append((mime, _decode_data(str(data))))
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            found.extend(_walk_parts(part))
    return found


def _strip_css(text: str) -> str:
    cleaned = text
    for _ in range(16):
        nxt = re.sub(r"\{[^{}]*\}", " ", cleaned)
        if nxt == cleaned:
            break
        cleaned = nxt
    cleaned = re.sub(r"[{}]", " ", cleaned)
    cleaned = re.sub(
        r"@(?i:media|import|font-face|supports)\b[^@A-ZÁÉÍÓÚÀÃÕÂÊÔÇ]*",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"!important", " ", cleaned, flags=re.I)
    return re.sub(r"\b(?:table\.body|externalclass|#messageviewbody)\b[\w.-]*", " ", cleaned, flags=re.I)


def _is_css_line(line: str) -> bool:
    folded = line.casefold()
    if not any(mark in folded for mark in (
        "!important", "@media", "table.body", "prefers-color-scheme",
        "externalclass", "font-size:", "max-width:", "line-height:", "#messageviewbody",
    )):
        return False
    return len(re.findall(r"[A-Za-zÀ-ÿ]{4,}", line)) < 3


def _normalize_text(text: str) -> str:
    text = re.sub(r",(?=[A-ZÁÉÍÓÚÀÃÕÂÊÔÇ][a-zà-ú])", ",\n", text)
    text = re.sub(r"(?<=[.!?])(?=[A-ZÁÉÍÓÚÀÃÕÂÊÔÇ][a-zà-ú])", "\n", text)
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line and not _is_css_line(line):
            lines.append(line)
    return "\n\n".join(lines)


def _html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<!--.*?-->", " ", value)
    text = re.sub(r"(?is)<(script|style|head)\b[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<style\b[^>]*>.*?(?=<body\b)", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|blockquote|table|section|article)>", "\n", text)
    text = re.sub(r"(?i)</td>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_text(_strip_css(html.unescape(text)))


def _plain_to_text(value: str) -> str:
    if re.search(r"(?i)</?(html|body|p|div|table|br)\b", value):
        return _html_to_text(value)
    return _normalize_text(_strip_css(html.unescape(value)))


def _message_body(payload: dict) -> str:
    parts = _walk_parts(payload)
    htmls = [text for text in (_html_to_text(body) for mime, body in parts if "html" in mime) if text]
    plains = [text for text in (_plain_to_text(body) for mime, body in parts if mime.startswith("text/plain")) if text]
    if htmls:
        return max(htmls, key=len)
    if plains:
        return plains[0]
    return ""


def _header(headers: list | None, name: str) -> str:
    for header in headers or []:
        if str(header.get("name") or "").casefold() == name.casefold():
            return str(header.get("value") or "").strip()
    return ""


def _reply_from_message(message: dict) -> dict:
    payload = message.get("payload") or {}
    headers = payload.get("headers")
    received = _message_date(message)
    return {
        "sender": _header(headers, "From") or _from_address(headers),
        "subject": _header(headers, "Subject"),
        "body": _message_body(payload),
        "sent_at": received.isoformat() if received else None,
    }


def fetch_reply(account: GoogleAccount, thread_id: str | None, contact_email: str | None, sent_at: datetime | None) -> dict | None:
    our_email = (account.email or "").casefold()
    if thread_id:
        thread = _gmail_get(account, f"/threads/{thread_id}", {"format": "full"})
        inbound = []
        for message in (thread or {}).get("messages") or []:
            sender = _from_address((message.get("payload") or {}).get("headers"))
            if sender and sender != our_email:
                inbound.append(message)
        if inbound:
            return _reply_from_message(inbound[-1])
    if not contact_email:
        return None
    listed = _gmail_get(account, "/messages", {"q": _reply_query(contact_email, sent_at), "maxResults": 1})
    items = (listed or {}).get("messages") or []
    if not items:
        return None
    message = _gmail_get(account, f"/messages/{items[0]['id']}", {"format": "full"})
    return _reply_from_message(message) if message else None


def _folded(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value)
    return "".join(char for char in stripped if not unicodedata.combining(char)).casefold()


_REJECTION_MARKS = (
    "nao iremos avancar",
    "nao vamos avancar",
    "nao avancaremos",
    "nao continuaremos",
    "nao seguiremos com",
    "nao foste selecionad",
    "nao foi selecionad",
    "nao fomos selecionad",
    "nao seras selecionad",
    "nao passaste a proxima",
    "will not be moving forward",
    "won't be moving forward",
    "will not be progressing",
    "not moving forward with your",
    "we will not proceed",
    "not been selected",
    "not been successful",
    "other candidates",
    "position has been filled",
    "we regret to inform",
)


def is_rejection(subject: str, body: str) -> bool:
    blob = _folded(f"{subject}\n{body}")
    return any(mark in blob for mark in _REJECTION_MARKS)


def status_for_reply(reply: dict | None) -> str:
    if reply and is_rejection(str(reply.get("subject") or ""), str(reply.get("body") or "")):
        return "rejected"
    return "replied"
