import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.User import User, UserCv


def save_cv(db: Session, user: User, filename: str, content: bytes, candidate_name: str | None, skills: list[str]) -> UserCv:
    cv = db.get(UserCv, user.id_user)
    if cv is None:
        cv = UserCv(id_user=user.id_user)
        db.add(cv)
    cv.filename = Path(filename).name[:255] or "CV"
    cv.content = content
    cv.candidate_name = candidate_name
    cv.skills_json = json.dumps(skills)
    cv.uploaded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cv)
    return cv


def get_cv(db: Session, user: User) -> UserCv | None:
    return db.get(UserCv, user.id_user)


def delete_cv(db: Session, user: User) -> None:
    db.query(UserCv).filter(UserCv.id_user == user.id_user).delete()
    db.commit()


def cv_info(cv: UserCv | None) -> dict | None:
    if cv is None:
        return None
    return {
        "filename": cv.filename,
        "candidate_name": cv.candidate_name,
        "skills": json.loads(cv.skills_json or "[]"),
        "uploaded_at": cv.uploaded_at.isoformat() if cv.uploaded_at else None,
    }
