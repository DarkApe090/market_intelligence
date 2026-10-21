import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.controllers.Auth import set_state_cookie
from app.database.connection import get_db
from app.models.User import User
from app.services import Auth, GoogleMail
from app.services.GoogleMail import GoogleError
from app.services.Quota import consume_quota

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/google", tags=["Google"])


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str
    attach_cv: bool = True


def _handoff(path: str = "/", session_token: str | None = None):
    return Auth.frontend_handoff(path, session_token)


@router.get("/status")
def google_status(user: User = Depends(Auth.get_current_user), db: Session = Depends(get_db)):
    return GoogleMail.status(db, user)


@router.get("/connect")
def connect(request: Request, db: Session = Depends(get_db)):
    user = Auth.user_from_token(db, request.cookies.get(Auth.SESSION_COOKIE))
    if user is None:
        return _handoff("/?auth=error")
    try:
        url, cookie = Auth.build_auth_url("gmail", login_hint=user.email, redirect_uri=Auth.callback_uri(request))
    except Auth.AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    response = RedirectResponse(url)
    set_state_cookie(response, cookie)
    return response


@router.get("/auth-url")
def auth_url(request: Request, user: User = Depends(Auth.get_current_user)):
    try:
        url, cookie = Auth.build_auth_url("gmail", login_hint=user.email, redirect_uri=Auth.callback_uri(request))
    except Auth.AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    response = JSONResponse({"url": url})
    set_state_cookie(response, cookie)
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    """Ponto único de retorno da Google, usado no login e na ligação do Gmail."""
    try:
        purpose, redirect_uri, verifier = Auth.split_oauth_state(state)
    except Auth.AuthError:
        logger.warning("OAuth callback rejected: invalid state")
        return _handoff("/?auth=error")

    if error or not code:
        return _handoff(f"/?{'google' if purpose == 'gmail' else 'auth'}=denied")

    if purpose == "login":
        try:
            payload = Auth.exchange_code(code, redirect_uri=redirect_uri, code_verifier=verifier)
            user = Auth.upsert_user(db, Auth.fetch_userinfo(payload["access_token"]))
        except Auth.AuthError as exc:
            logger.warning("OAuth callback rejected: %s", exc)
            return _handoff("/?auth=error")
        return _handoff("/", Auth.create_session(db, user))

    user = Auth.user_from_token(db, request.cookies.get(Auth.SESSION_COOKIE))
    if user is None:
        return _handoff("/?auth=error")
    try:
        GoogleMail.connect(db, user, code, redirect_uri=redirect_uri, code_verifier=verifier)
    except GoogleError:
        logger.warning("OAuth callback rejected: Gmail connect failed")
        return _handoff("/?google=error")
    return _handoff("/?google=connected")


@router.post("/disconnect")
def disconnect(user: User = Depends(Auth.get_current_user), db: Session = Depends(get_db)):
    GoogleMail.disconnect(db, user)
    return GoogleMail.status(db, user)


@router.post("/send")
def send(
    payload: SendEmailRequest,
    user: User = Depends(Auth.get_current_user),
    db: Session = Depends(get_db),
):
    consume_quota(db, user, "send")
    try:
        GoogleMail.send_email(db, user, payload.to, payload.subject, payload.body, payload.attach_cv)
    except GoogleError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"sent": True}
