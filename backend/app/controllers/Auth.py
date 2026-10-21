from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import get_db
from app.models.User import User
from app.services import Auth, GoogleMail
from app.services.UserCv import cv_info, get_cv


router = APIRouter(prefix="/auth", tags=["Auth"])


def set_state_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        Auth.STATE_COOKIE,
        value,
        max_age=settings.oauth_state_minutes * 60,
        **Auth.cookie_kwargs(),
    )


def _oauth_redirect(url: str, cookie: str) -> RedirectResponse:
    response = RedirectResponse(url)
    set_state_cookie(response, cookie)
    return response


@router.get("/login")
def login(request: Request, accepted: int = 0):
    """Redirect de página inteira: o cookie de state fica first-party no backend."""
    Auth.require_terms_accepted(accepted)
    try:
        url, cookie = Auth.build_auth_url("login", redirect_uri=Auth.callback_uri(request))
    except Auth.AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _oauth_redirect(url, cookie)


@router.get("/login-url")
def login_url(request: Request, response: Response, accepted: int = 0):
    Auth.require_terms_accepted(accepted)
    try:
        url, cookie = Auth.build_auth_url("login", redirect_uri=Auth.callback_uri(request))
    except Auth.AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    set_state_cookie(response, cookie)
    return {"url": url}


@router.get("/me")
def me(user: User = Depends(Auth.get_current_user), db: Session = Depends(get_db)):
    return {
        "user": {"email": user.email, "name": user.name, "picture": user.picture_url},
        "cv": cv_info(get_cv(db, user)),
        "google": GoogleMail.status(db, user),
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    Auth.delete_session(db, request.cookies.get(Auth.SESSION_COOKIE))
    Auth.clear_cookie(response, Auth.SESSION_COOKIE)
    return {"message": "Sessão terminada"}


@router.get("/export")
def export_me(db: Session = Depends(get_db), user: User = Depends(Auth.get_current_user)):
    return Auth.export_account(db, user)


@router.delete("/account")
def delete_me(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(Auth.get_current_user),
):
    Auth.delete_account(db, user)
    Auth.clear_cookie(response, Auth.SESSION_COOKIE)
    return {"message": "Conta apagada"}
