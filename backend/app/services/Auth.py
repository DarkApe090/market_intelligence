import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.database.connection import get_db
from app.models.Company import Company
from app.models.Contact import Contact
from app.models.User import AuthSession, User


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
LOGIN_SCOPES = "openid email profile"
GMAIL_SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"
SESSION_COOKIE = "ponto_session"
STATE_COOKIE = "ponto_oauth_state"
REQUEST_TIMEOUT = 20
KEY_FILE = BASE_DIR / "data" / "secret.key"


class AuthError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def _fernet() -> Fernet:
    key = settings.token_encryption_key.strip()
    if not key:
        if KEY_FILE.exists():
            key = KEY_FILE.read_text(encoding="utf-8").strip()
        else:
            KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key().decode()
            KEY_FILE.write_text(key, encoding="utf-8")
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise AuthError("NÃ£o foi possÃ­vel ler as credenciais guardadas. Liga o Gmail de novo.") from error


def build_auth_url(purpose: str, login_hint: str | None = None) -> tuple[str, str]:
    """Devolve o URL da Google e o valor do cookie que liga o pedido ao browser."""
    if not is_configured():
        raise AuthError("Falta configurar GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no backend/.env.")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if purpose == "gmail":
        params.update(scope=GMAIL_SCOPES, access_type="offline", prompt="consent")
        if login_hint:
            params["login_hint"] = login_hint
    else:
        params.update(scope=LOGIN_SCOPES, prompt="select_account")
    return f"{AUTH_URL}?{urlencode(params)}", f"{purpose}.{state}"


def split_state_cookie(cookie: str | None, state: str) -> str:
    """Valida o state devolvido pela Google contra o cookie e devolve o propÃ³sito."""
    purpose, _, expected = (cookie or "").partition(".")
    if purpose not in {"login", "gmail"} or not expected or not state:
        raise AuthError("Pedido de autorizaÃ§Ã£o invÃ¡lido ou expirado.")
    if not secrets.compare_digest(expected, state):
        raise AuthError("Pedido de autorizaÃ§Ã£o invÃ¡lido ou expirado.")
    return purpose


def exchange_code(code: str) -> dict:
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise AuthError("NÃ£o foi possÃ­vel contactar a Google.") from error
    if response.status_code != 200:
        raise AuthError("A Google recusou a autorizaÃ§Ã£o.")
    return response.json()


def fetch_userinfo(access_token: str) -> dict:
    try:
        response = httpx.get(
            USERINFO_URL,
            headers={"Authorization": "Bearer " + access_token},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise AuthError("NÃ£o foi possÃ­vel contactar a Google.") from error
    if response.status_code != 200:
        raise AuthError("NÃ£o foi possÃ­vel obter o perfil da Google.")
    info = response.json()
    if not info.get("sub") or not info.get("email") or info.get("email_verified") is False:
        raise AuthError("A conta Google nÃ£o tem um email verificado.")
    return info


def upsert_user(db: Session, info: dict) -> User:
    user = db.query(User).filter(User.google_sub == info["sub"]).first()
    if user is None:
        first_user = db.query(User).count() == 0
        user = User(google_sub=info["sub"], email=info["email"])
        db.add(user)
        db.flush()
        if first_user:
            # Os dados anteriores ao multiutilizador passam para o primeiro utilizador.
            db.query(Company).filter(Company.id_user.is_(None)).update({Company.id_user: user.id_user})
            db.query(Contact).filter(Contact.id_user.is_(None)).update({Contact.id_user: user.id_user})
    user.email = info["email"]
    user.name = info.get("name")
    user.picture_url = info.get("picture")
    db.commit()
    db.refresh(user)
    return user


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    db.query(AuthSession).filter(AuthSession.expires_at < now).delete()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        token_hash=_hash(token),
        id_user=user.id_user,
        expires_at=now + timedelta(days=settings.session_days),
    ))
    db.commit()
    return token


def delete_session(db: Session, token: str | None) -> None:
    if token:
        db.query(AuthSession).filter(AuthSession.token_hash == _hash(token)).delete()
        db.commit()


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.get(AuthSession, _hash(token))
    if session is None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.id_user)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_token(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="SessÃ£o invÃ¡lida ou expirada.")
    return user


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
