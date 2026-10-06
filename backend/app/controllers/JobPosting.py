from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.JobPosting import (CreateJobPosting, UpdateJobPosting, JobPostingResponse)
from app.services.JobPosting import (create_jobposting, get_jobposting, get_jobpostings, update_jobposting, delete_jobposting)

router = APIRouter(
    prefix = "/jobpostings",
    tags=["JobPostings"]
)

@router.post("/", response_model=JobPostingResponse)
def create(jobposting: CreateJobPosting, db: Session = Depends(get_db)):

    return create_jobposting(db, jobposting)

@router.get("/{jobposting_id}", response_model= JobPostingResponse)
def get(jobposting_id: int, db: Session = Depends(get_db)):
    
    jobposting = get_jobposting(db, jobposting_id)

    if jobposting is None:
        raise HTTPException(
            status_code = 404, 
            detail = "JobPosting not found"
        )
    
    return jobposting

@router.get("/", response_model=list[JobPostingResponse])
def get_all(db: Session = Depends(get_db)):

    return get_jobpostings(db)

@router.put("/{jobposting_id}", response_model=JobPostingResponse)
def update(
    jobposting_id: int,
    jobposting: UpdateJobPosting,
    db: Session = Depends(get_db)
): 

    updated_jobposting = update_jobposting(
        db,
        jobposting_id,
        jobposting
    )

    if updated_jobposting is None:
        raise HTTPException(
            status_code = 404,
            detail = "JobPosting not found"
        )

    return updated_jobposting

@router.delete("/{jobposting_id}")
def delete(jobposting_id: int, db: Session = Depends(get_db)):
    
    deleted = delete_jobposting(db, jobposting_id)

    if not deleted:
        raise HTTPException(
            status_code = 404,
            detail = "JobPosting not found"
        )

    return {"message": "JobPosting deleted successfully"}