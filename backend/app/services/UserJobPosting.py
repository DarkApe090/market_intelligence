from datetime import datetime

from sqlalchemy.orm import Session

from app.models.JobPosting import JobPosting
from app.models.User import User
from app.models.UserJobPosting import UserJobPosting
from app.schemas.UserJobPosting import CreateUserJobPosting, UpdateUserJobPosting


def _pk(id_user: int, id_jobPosting: int) -> dict:
    return {"id_user": id_user, "id_jobPosting": id_jobPosting}


def create_user_jobposting(db: Session, id_user: int, user_jobposting: CreateUserJobPosting) -> UserJobPosting:
    if db.get(User, id_user) is None:
        raise LookupError("User not found")

    if db.get(JobPosting, user_jobposting.id_jobPosting) is None:
        raise LookupError("Job posting not found")

    existing_user_jobposting = db.get(UserJobPosting, _pk(id_user, user_jobposting.id_jobPosting))
    if existing_user_jobposting is not None:
        return existing_user_jobposting

    db_user_jobposting = UserJobPosting(
        id_user=id_user,
        id_jobPosting=user_jobposting.id_jobPosting,
        seen_at=None,
    )
    db.add(db_user_jobposting)
    db.commit()
    db.refresh(db_user_jobposting)
    return db_user_jobposting


def get_user_jobposting(db: Session, id_user: int, id_jobPosting: int) -> UserJobPosting | None:
    return db.get(UserJobPosting, _pk(id_user, id_jobPosting))


def get_user_jobpostings(db: Session, id_user: int) -> list[UserJobPosting]:
    return db.query(UserJobPosting).filter(UserJobPosting.id_user == id_user).all()


def update_user_jobposting(
    db: Session,
    id_user: int,
    id_jobPosting: int,
    user_jobposting: UpdateUserJobPosting,
) -> UserJobPosting | None:
    db_user_jobposting = db.get(UserJobPosting, _pk(id_user, id_jobPosting))
    if db_user_jobposting is None:
        return None

    if "seen_at" in user_jobposting.model_fields_set:
        db_user_jobposting.seen_at = user_jobposting.seen_at

    db.commit()
    db.refresh(db_user_jobposting)
    return db_user_jobposting


def mark_jobposting_as_seen(db: Session, id_user: int, id_jobPosting: int) -> UserJobPosting | None:
    db_user_jobposting = db.get(UserJobPosting, _pk(id_user, id_jobPosting))
    if db_user_jobposting is None:
        return None

    db_user_jobposting.seen_at = datetime.now()
    db.commit()
    db.refresh(db_user_jobposting)
    return db_user_jobposting


def list_job_urls(db: Session, id_user: int) -> list[str]:
    rows = (
        db.query(JobPosting.url_jobPosting)
        .join(UserJobPosting, UserJobPosting.id_jobPosting == JobPosting.id_jobPosting)
        .filter(UserJobPosting.id_user == id_user)
        .all()
    )
    return [url for url, in rows if url]


def delete_user_jobposting(db: Session, id_user: int, id_jobPosting: int) -> bool:
    db_user_jobposting = db.get(UserJobPosting, _pk(id_user, id_jobPosting))
    if db_user_jobposting is None:
        return False

    db.delete(db_user_jobposting)
    db.commit()
    return True
