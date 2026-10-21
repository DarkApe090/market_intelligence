import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.User import User, UserCv


def save_cv(
    db: Session,
    user: User,
    filename: str,
    content: bytes,
    candidate_name: str | None,
    skills: list[str],
    profile: dict | None = None,
) -> UserCv:
    cv = db.get(UserCv, user.id_user)
    if cv is None:
        cv = UserCv(id_user=user.id_user)
        db.add(cv)
    cv.filename = Path(filename).name[:255] or "CV"
    cv.content = content
    cv.candidate_name = candidate_name
    cv.skills_json = json.dumps(skills)
    cv.profile_json = json.dumps(profile, ensure_ascii=False) if profile else None
    cv.uploaded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cv)
    return cv


def get_cv(db: Session, user: User) -> UserCv | None:
    return db.get(UserCv, user.id_user)


def load_profile(cv: UserCv | None) -> dict | None:
    if cv is None or not cv.profile_json:
        return None
    try:
        profile = json.loads(cv.profile_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(profile, dict) or not profile.get("areas"):
        return None
    return profile


def save_profile(db: Session, cv: UserCv, profile: dict, skills: list[str]) -> None:
    cv.profile_json = json.dumps(profile, ensure_ascii=False)
    cv.skills_json = json.dumps(skills)
    db.commit()


def delete_cv(db: Session, user: User) -> None:
    db.query(UserCv).filter(UserCv.id_user == user.id_user).delete()
    db.commit()


def cv_info(cv: UserCv | None) -> dict | None:
    if cv is None:
        return None
    profile = load_profile(cv)
    areas = []
    for area in (profile or {}).get("areas") or []:
        if isinstance(area, dict) and str(area.get("name") or "").strip():
            areas.append({
                "name": str(area["name"]).strip(),
                "matched_skills": [
                    str(skill).strip()
                    for skill in (area.get("matched_skills") or [])
                    if str(skill).strip()
                ],
            })
    return {
        "filename": cv.filename,
        "candidate_name": cv.candidate_name,
        "skills": json.loads(cv.skills_json or "[]"),
        "areas": areas,
        "uploaded_at": cv.uploaded_at.isoformat() if cv.uploaded_at else None,
    }
