from fastapi import APIRouter

from app.legal import html_page

router = APIRouter(tags=["Legal"])


@router.get("/privacidade")
def privacy():
    return html_page("privacidade")


@router.get("/termos")
def terms():
    return html_page("termos")
