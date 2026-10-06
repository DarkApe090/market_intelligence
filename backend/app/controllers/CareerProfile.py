from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.ai.llm import LLMError
from app.ai.outreach_graph import outreach_graph
from app.models.User import User
from app.schemas.CareerProfile import DraftRequest, DraftResponse, SaveSuggestion, SaveSuggestionResponse
from app.services.Auth import get_current_user
from app.services.CareerProfile import MAX_CV_BYTES, analyze_cv
from app.services.ContactEnrichment import enrich_company
from app.services.OutreachSuggestion import save_suggestion
from app.services.UserCv import cv_info, delete_cv, get_cv, save_cv

router = APIRouter(
    prefix="/career-profile",
    tags=["Career Profile"],
)


class StoredAnalysisRequest(BaseModel):
    location: str = "Portugal"


def _skills(analysis: dict) -> list[str]:
    return list(dict.fromkeys(skill for area in analysis["areas"] for skill in area["matched_skills"]))


@router.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    location: str = Form(default="Portugal"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        content = file.file.read(MAX_CV_BYTES + 1)
        analysis = analyze_cv(file.filename or "", content, location=location)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        file.file.close()

    save_cv(db, user, file.filename or "CV", content, analysis["candidate_name"], _skills(analysis))
    analysis["cv_saved"] = True
    return analysis


@router.post("/analyze-stored")
def analyze_stored(
    payload: StoredAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cv = get_cv(db, user)
    if cv is None:
        raise HTTPException(status_code=404, detail="Ainda não carregaste um CV.")

    try:
        analysis = analyze_cv(cv.filename, cv.content, location=payload.location)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    analysis["cv_saved"] = True
    return analysis


@router.get("/cv")
def stored_cv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cv_info(get_cv(db, user))


@router.delete("/cv")
def remove_cv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_cv(db, user)
    return {"message": "CV removido"}


@router.post("/suggestions/save", response_model=SaveSuggestionResponse)
def save(
    suggestion: SaveSuggestion,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = save_suggestion(db, suggestion, user)
    background_tasks.add_task(enrich_company, saved["id_company"])
    return saved


@router.post("/suggestions/draft", response_model=DraftResponse)
def draft_application(payload: DraftRequest, user: User = Depends(get_current_user)):
    try:
        state = outreach_graph.invoke(payload.model_dump())
    except LLMError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return DraftResponse(
        fit_score=state["fit_score"],
        fit_reason=state.get("fit_reason", ""),
        subject=state.get("subject"),
        body=state.get("body"),
        skipped="body" not in state,
    )
