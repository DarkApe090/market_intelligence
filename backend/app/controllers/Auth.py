from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


@router.get("/login-url")
def login_url(response: Response):
    try:
        url, cookie = Auth.build_auth_url("login")
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
    response.delete_cookie(Auth.SESSION_COOKIE, path="/")
    return {"message": "Sessão terminada"}
