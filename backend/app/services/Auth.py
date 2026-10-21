import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.database.connection import get_db
from app.models.Company import Company
from app.models.Contact import Contact
from app.models.User import AuthSession, User

logger = logging.getLogger(__name__)


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
LOGIN_SCOPES = "openid email profile"
GMAIL_SCOPES = "openid email https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly"
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
        raise AuthError("Não foi possível ler as credenciais guardadas. Liga o Gmail de novo.") from error


def _state_secret() -> bytes:
    raw = settings.token_encryption_key.strip()
    if not raw:
        _fernet()
        raw = KEY_FILE.read_text(encoding="utf-8").strip()
    return hashlib.sha256(raw.encode()).digest()


def _b64url(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _b64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode()


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _is_loopback(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return host in {"localhost", "127.0.0.1", "::1"}


def callback_uri(request) -> str:
    """Em produção usa GOOGLE_REDIRECT_URI; em local segue o host do pedido (localhost vs 127.0.0.1)."""
    configured = settings.google_redirect_uri.rstrip("/")
    if not _is_loopback(configured):
        return configured
    return str(request.base_url).rstrip("/") + "/google/callback"


def _sign_oauth_state(purpose: str, redirect_uri: str, verifier: str) -> str:
    issued = str(int(time.time()))
    nonce = secrets.token_urlsafe(16)
    payload = f"{purpose}.{issued}.{nonce}.{_b64url(redirect_uri)}.{verifier}"
    signature = hmac.new(_state_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{signature}"


def build_auth_url(purpose: str, login_hint: str | None = None, redirect_uri: str | None = None) -> tuple[str, str]:
    """Devolve o URL da Google e o state assinado (válido em localhost e em produção)."""
    if not is_configured():
        raise AuthError("Falta configurar GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no backend/.env.")
    if purpose not in {"login", "gmail"}:
        raise AuthError("Pedido de autorização inválido ou expirado.")

    redirect_uri = (redirect_uri or settings.google_redirect_uri).rstrip("/")
    verifier, challenge = _pkce_pair()
    state = _sign_oauth_state(purpose, redirect_uri, verifier)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if purpose == "gmail":
        params.update(scope=GMAIL_SCOPES, access_type="offline", prompt="consent")
        if login_hint:
            params["login_hint"] = login_hint
    else:
        params.update(scope=LOGIN_SCOPES, prompt="select_account")
    return f"{AUTH_URL}?{urlencode(params)}", state


def split_oauth_state(state: str) -> tuple[str, str, str]:
    """Devolve propósito, redirect_uri e code_verifier do state assinado."""
    parts = (state or "").split(".")
    if len(parts) != 6:
        raise AuthError("Pedido de autorização inválido ou expirado.")
    purpose, issued, nonce, redirect_b64, verifier, signature = parts
    if purpose not in {"login", "gmail"} or not issued.isdigit() or not nonce or not verifier:
        raise AuthError("Pedido de autorização inválido ou expirado.")
    payload = f"{purpose}.{issued}.{nonce}.{redirect_b64}.{verifier}"
    expected = hmac.new(_state_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not secrets.compare_digest(expected, signature):
        raise AuthError("Pedido de autorização inválido ou expirado.")
    age = abs(time.time() - int(issued))
    if age > settings.oauth_state_minutes * 60:
        raise AuthError("Pedido de autorização inválido ou expirado.")
    try:
        return purpose, _b64url_decode(redirect_b64), verifier
    except Exception as error:
        raise AuthError("Pedido de autorização inválido ou expirado.") from error


def split_state_cookie(cookie: str | None, state: str) -> str:
    del cookie
    purpose, _, _ = split_oauth_state(state)
    return purpose


def cookie_kwargs(**extra):
    return {
        "httponly": True,
        "samesite": settings.cookie_samesite,
        "secure": settings.cookie_secure_flag,
        "path": "/",
        **extra,
    }


def clear_cookie(response, name: str) -> None:
    response.delete_cookie(
        name,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure_flag,
    )


def exchange_code(code: str, redirect_uri: str | None = None, code_verifier: str | None = None) -> dict:
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": (redirect_uri or settings.google_redirect_uri).rstrip("/"),
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    try:
        response = httpx.post(TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT)
    except httpx.HTTPError as error:
        logger.warning("Google token request failed: %s", error)
        raise AuthError("Não foi possível contactar a Google.") from error
    if response.status_code != 200:
        try:
            detail = response.json()
        except ValueError:
            detail = {}
        logger.warning(
            "Google token exchange failed (%s): %s %s",
            response.status_code,
            detail.get("error") if isinstance(detail, dict) else detail,
            detail.get("error_description") if isinstance(detail, dict) else response.text[:200],
        )
        raise AuthError("A Google recusou a autorização.")
    return response.json()


def fetch_userinfo(access_token: str) -> dict:
    try:
        response = httpx.get(
            USERINFO_URL,
            headers={"Authorization": "Bearer " + access_token},
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        logger.warning("Google userinfo request failed: %s", error)
        raise AuthError("Não foi possível contactar a Google.") from error
    if response.status_code != 200:
        raise AuthError("Não foi possível obter o perfil da Google.")
    info = response.json()
    if not info.get("sub") or not info.get("email") or info.get("email_verified") is False:
        raise AuthError("A conta Google não tem um email verificado.")
    return info


def upsert_user(db: Session, info: dict) -> User:
    user = db.query(User).filter(User.google_sub == info["sub"]).first()
    if user is None:
        first_user = db.query(User).count() == 0
        user = User(google_sub=info["sub"], email=info["email"])
        db.add(user)
        db.flush()
        if first_user:
            db.query(Company).filter(Company.id_user.is_(None)).update({Company.id_user: user.id_user})
            db.query(Contact).filter(Contact.id_user.is_(None)).update({Contact.id_user: user.id_user})
    user.email = info["email"]
    user.name = info.get("name")
    user.picture_url = info.get("picture")
    if user.terms_accepted_at is None:
        user.terms_accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def require_terms_accepted(accepted: int) -> None:
    if accepted != 1:
        raise HTTPException(
            status_code=400,
            detail="Aceita os termos e a política de privacidade para entrar.",
        )


def export_account(db: Session, user: User) -> dict:
    from app.services.Company import get_companies
    from app.services.CompanyContact import get_outreach_contacts
    from app.services.UserCv import cv_info, get_cv

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "terms_accepted_at": user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
        },
        "cv": cv_info(get_cv(db, user)),
        "companies": [
            {"name": company.name_company, "website": company.website_url}
            for company in get_companies(db, user)
        ],
        "contacts": [
            {
                "company": row["name_company"],
                "website": row["website_url"],
                "name": row["name_contact"],
                "email": row["email"],
                "role": row["role_contact"],
                "job_title": row["job_title"],
                "status": row["outreach_status"],
            }
            for row in get_outreach_contacts(db, user.id_user)
        ],
    }


def delete_account(db: Session, user: User) -> None:
    from app.models.CompanyLocation import CompanyLocation
    from app.models.ContactCompany import CompanyContact
    from app.models.ContactJobPosting import ContactJobPosting
    from app.models.UserJobPosting import UserJobPosting

    id_user = user.id_user
    companies = db.query(Company).filter(Company.id_user == id_user).all()
    for company in companies:
        contact_ids = [
            row.id_contact
            for row in db.query(CompanyContact.id_contact)
            .filter(CompanyContact.id_company == company.id_company)
            .all()
        ]
        db.query(CompanyContact).filter(CompanyContact.id_company == company.id_company).delete()
        for id_contact in contact_ids:
            still_linked = (
                db.query(CompanyContact)
                .filter(CompanyContact.id_contact == id_contact)
                .first()
            )
            if still_linked is None:
                db.query(ContactJobPosting).filter(ContactJobPosting.id_contact == id_contact).delete()
                db.query(Contact).filter(Contact.id_contact == id_contact).delete()
        db.query(CompanyLocation).filter(CompanyLocation.id_company == company.id_company).delete()
        db.delete(company)

    for contact in db.query(Contact).filter(Contact.id_user == id_user).all():
        db.query(ContactJobPosting).filter(ContactJobPosting.id_contact == contact.id_contact).delete()
        db.query(CompanyContact).filter(CompanyContact.id_contact == contact.id_contact).delete()
        db.delete(contact)

    db.query(UserJobPosting).filter(UserJobPosting.id_user == id_user).delete()
    db.delete(user)
    db.commit()


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
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return user


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        **cookie_kwargs(),
    )


def frontend_handoff(path: str = "/", session_token: str | None = None):
    """200 HTML: o cookie da sessão fica first-party; o 307 para o frontend perdia-o."""
    import html
    import json

    from fastapi.responses import HTMLResponse

    target = settings.frontend_url.rstrip("/") + (path if path.startswith("/") else f"/{path}")
    page = (
        "<!DOCTYPE html><html><head>"
        f'<meta http-equiv="refresh" content="0;url={html.escape(target, quote=True)}">'
        "</head><body>"
        f"<script>location.replace({json.dumps(target)})</script>"
        "</body></html>"
    )
    response = HTMLResponse(page)
    clear_cookie(response, STATE_COOKIE)
    if session_token:
        set_session_cookie(response, session_token)
    return response
