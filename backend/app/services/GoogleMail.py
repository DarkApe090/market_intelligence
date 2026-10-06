import base64
import time
from email.message import EmailMessage
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.User import GoogleAccount, User
from app.services import Auth
from app.services.UserCv import get_cv


TOKEN_URL = Auth.TOKEN_URL
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
REQUEST_TIMEOUT = 20

# Cache em memória dos access tokens (curta duração) por utilizador.
_access_tokens: dict[int, tuple[str, float]] = {}


class GoogleError(Exception):
    pass


def is_configured() -> bool:
    return Auth.is_configured()


def connect(db: Session, user: User, code: str) -> None:
    try:
        payload = Auth.exchange_code(code)
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


def disconnect(db: Session, user: User) -> None:
    db.query(GoogleAccount).filter(GoogleAccount.id_user == user.id_user).delete()
    db.commit()
    _access_tokens.pop(user.id_user, None)


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


def status(db: Session, user: User) -> dict:
    account = db.get(GoogleAccount, user.id_user)
    return {
        "configured": is_configured(),
        "connected": account is not None,
        "email": account.email if account else None,
    }


def build_message(to: str, subject: str, body: str, sender: str | None, cv) -> EmailMessage:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    message.set_content(body)

    if cv is not None:
        is_pdf = Path(cv.filename).suffix.casefold() == ".pdf"
        subtype = "pdf" if is_pdf else "vnd.openxmlformats-officedocument.wordprocessingml.document"
        message.add_attachment(cv.content, maintype="application", subtype=subtype, filename=cv.filename)
    return message


def send_email(db: Session, user: User, to: str, subject: str, body: str, attach_cv: bool = True) -> None:
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
