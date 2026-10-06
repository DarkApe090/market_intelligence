from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.controllers.Auth import set_state_cookie
from app.core.config import settings
from app.database.connection import get_db
from app.models.User import User
from app.services import Auth, GoogleMail
from app.services.GoogleMail import GoogleError


router = APIRouter(prefix="/google", tags=["Google"])


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str
    attach_cv: bool = True


def _redirect(target: str) -> RedirectResponse:
    response = RedirectResponse(target)
    response.delete_cookie(Auth.STATE_COOKIE, path="/")
    return response


@router.get("/status")
def google_status(user: User = Depends(Auth.get_current_user), db: Session = Depends(get_db)):
    return GoogleMail.status(db, user)


@router.get("/auth-url")
def auth_url(user: User = Depends(Auth.get_current_user)):
    try:
        url, cookie = Auth.build_auth_url("gmail", login_hint=user.email)
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
    base = settings.frontend_url.rstrip("/")
    try:
        purpose = Auth.split_state_cookie(request.cookies.get(Auth.STATE_COOKIE), state)
    except Auth.AuthError:
        return _redirect(f"{base}/?auth=error")

    if error or not code:
        return _redirect(f"{base}/?{'google' if purpose == 'gmail' else 'auth'}=denied")

    if purpose == "login":
        try:
            payload = Auth.exchange_code(code)
            user = Auth.upsert_user(db, Auth.fetch_userinfo(payload["access_token"]))
        except Auth.AuthError:
            return _redirect(f"{base}/?auth=error")
        response = _redirect(f"{base}/")
        Auth.set_session_cookie(response, Auth.create_session(db, user))
        return response

    user = Auth.user_from_token(db, request.cookies.get(Auth.SESSION_COOKIE))
    if user is None:
        return _redirect(f"{base}/?auth=error")
    try:
        GoogleMail.connect(db, user, code)
    except GoogleError:
        return _redirect(f"{base}/?google=error")
    return _redirect(f"{base}/?google=connected")


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
    try:
        GoogleMail.send_email(db, user, payload.to, payload.subject, payload.body, payload.attach_cv)
    except GoogleError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"sent": True}
