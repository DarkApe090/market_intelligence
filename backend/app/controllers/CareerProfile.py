import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.ai.llm import LLMError
from app.ai.outreach_graph import outreach_graph
from app.models.User import User
from app.schemas.CareerProfile import DraftRequest, DraftResponse, ProfileEdit, SaveSuggestion, SaveSuggestionResponse
from app.services.Auth import get_current_user
from app.services.CareerProfile import MAX_CV_BYTES, edit_profile
from app.services.JobSearch import analyze_cv_stream
from app.services.Places import search_places
from app.services.CompanyContact import get_outreach_contacts
from app.services.ContactEnrichment import enrich_company
from app.services.OutreachSuggestion import save_suggestion
from app.services.Quota import consume_quota
from app.services.UserCv import cv_info, delete_cv, get_cv, load_profile, save_cv, save_profile
from app.services.UserJobPosting import list_job_urls

router = APIRouter(
    prefix="/career-profile",
    tags=["Career Profile"],
)


class StoredAnalysisRequest(BaseModel):
    location: str = "Portugal"
    exclude_companies: list[str] = []
    work_mode: str = ""
    schedule: str = ""


def _json_strings(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _skills(analysis: dict) -> list[str]:
    skills = [skill for area in analysis["areas"] for skill in area["matched_skills"]]
    return list(dict.fromkeys([*skills, *(analysis.get("languages") or [])]))


def _profile_payload(event: dict) -> dict:
    return {
        "candidate_name": event.get("candidate_name"),
        "areas": event.get("areas") or [],
        "languages": event.get("languages") or [],
        "llm_used": bool(event.get("llm_used")),
    }


def _listed_companies(db: Session, user: User, extra: list[str] | None = None) -> list[str]:
    names = [row["name_company"] for row in get_outreach_contacts(db, user.id_user)]
    return list(dict.fromkeys([*names, *(extra or [])]))


def _stream_analysis(events, on_profile=None):
    def generate():
        try:
            for event in events:
                if event.get("type") == "profile" and on_profile is not None:
                    on_profile(event)
                    event = {**event, "cv_saved": True}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as error:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(error)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    location: str = Form(default="Portugal"),
    exclude_companies: str = Form(default="[]"),
    work_mode: str = Form(default=""),
    schedule: str = Form(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        content = file.file.read(MAX_CV_BYTES + 1)
        events = analyze_cv_stream(
            file.filename or "",
            content,
            location=location,
            exclude_companies=_listed_companies(db, user, _json_strings(exclude_companies)),
            saved_urls=list_job_urls(db, user.id_user),
            work_mode=work_mode,
            schedule=schedule,
        )
        first = next(events)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        file.file.close()
    consume_quota(db, user, "analysis")

    def on_profile(event: dict) -> None:
        save_cv(
            db,
            user,
            file.filename or "CV",
            content,
            event.get("candidate_name"),
            _skills(event),
            _profile_payload(event),
        )

    def with_first():
        yield first
        yield from events

    return _stream_analysis(with_first(), on_profile)


@router.post("/analyze-stored")
def analyze_stored(
    payload: StoredAnalysisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cv = get_cv(db, user)
    if cv is None:
        raise HTTPException(status_code=404, detail="Ainda não carregaste um CV.")

    profile = load_profile(cv)
    try:
        events = analyze_cv_stream(
            cv.filename,
            cv.content,
            location=payload.location,
            exclude_companies=_listed_companies(db, user, payload.exclude_companies),
            saved_urls=list_job_urls(db, user.id_user),
            profile=profile,
            work_mode=payload.work_mode,
            schedule=payload.schedule,
        )
        first = next(events)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    consume_quota(db, user, "analysis")

    def on_profile(event: dict) -> None:
        if profile is None:
            save_cv(
                db,
                user,
                cv.filename,
                cv.content,
                event.get("candidate_name"),
                _skills(event),
                _profile_payload(event),
            )

    def with_first():
        yield first
        yield from events

    return _stream_analysis(with_first(), None if profile else on_profile)


@router.get("/places")
def places(q: str = "", user: User = Depends(get_current_user)):
    return search_places(q)


@router.put("/profile")
def update_profile(
    payload: ProfileEdit,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cv = get_cv(db, user)
    if cv is None:
        raise HTTPException(status_code=404, detail="Ainda não carregaste um CV.")
    profile = edit_profile(load_profile(cv), cv.candidate_name, [area.model_dump() for area in payload.areas])
    save_profile(db, cv, profile, _skills(profile))
    return _profile_payload(profile)


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
    if not saved.get("email") and not saved["already_in_outreach"]:
        background_tasks.add_task(enrich_company, saved["id_company"], None, True)
    return saved


@router.post("/suggestions/draft", response_model=DraftResponse)
def draft_application(
    payload: DraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consume_quota(db, user, "draft")
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
