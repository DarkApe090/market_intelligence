from sqlalchemy.orm import Session
from app.models.JobPosting import JobPosting 
from app.schemas.JobPosting import CreateJobPosting, UpdateJobPosting

def create_jobposting(db: Session, jobposting: CreateJobPosting) -> JobPosting:
    if jobposting.url_jobPosting is not None:
        existing_jobposting = (
            db.query(JobPosting)
            .filter(
                JobPosting.id_source == jobposting.id_source,
                JobPosting.url_jobPosting == jobposting.url_jobPosting,
            )
            .first()
        )

        if existing_jobposting is not None:
            return existing_jobposting

    db_jobposting = JobPosting(
        position_jobPosting=jobposting.position_jobPosting,
        id_source=jobposting.id_source,
        url_jobPosting=jobposting.url_jobPosting,
    )

    db.add(db_jobposting)
    db.commit()
    db.refresh(db_jobposting)

    return db_jobposting

def get_jobposting(db: Session, jobposting_id: int) -> JobPosting | None:
    return db.query(JobPosting).filter(JobPosting.id_jobPosting == jobposting_id).first()


def get_jobpostings(db: Session) -> list[JobPosting]:
    return db.query(JobPosting).all()

def update_jobposting(
    db: Session,
    jobposting_id: int,
    jobposting: UpdateJobPosting,
) -> JobPosting | None:

    db_jobposting = db.get(JobPosting, jobposting_id)

    if db_jobposting is None:
        return None

    db_jobposting.position_jobPosting = jobposting.position_jobPosting
    db_jobposting.id_source = jobposting.id_source

    if "url_jobPosting" in jobposting.model_fields_set:
        db_jobposting.url_jobPosting = jobposting.url_jobPosting

    db.commit()
    db.refresh(db_jobposting)

    return db_jobposting

def delete_jobposting(db: Session, jobposting_id: int) -> bool:
    db_jobposting = db.get(JobPosting, jobposting_id)

    if db_jobposting is None: 
        return False

    db.delete(db_jobposting)
    db.commit()

    return True
