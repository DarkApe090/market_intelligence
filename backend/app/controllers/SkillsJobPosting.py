from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.Skills import SkillResponse
from app.services.SkillsJobPosting import (
    create_skill_jobposting,
    get_jobposting_skills,
    delete_skill_jobposting,
)

router = APIRouter(
    prefix="/jobpostings",
    tags=["Job Posting Skills"],
)

@router.post("/{id_jobPosting}/skills/{id_skill}")
def create(
    id_jobPosting: int,
    id_skill: int,
    response: Response,
    db: Session = Depends(get_db),
): 
    try:
        association, created = create_skill_jobposting(
            db,
            id_skill,
            id_jobPosting,
        )
    except LookupError as error:
        raise HTTPException(
            status_code = 404,
            detail=str(error)
        )

    response.status_code = 201 if created else 200

    return {
        "id_skill": association.id_skill,
        "id_jobPosting": association.id_jobPosting,
        "created": created,
    }

@router.get("/{id_jobPosting}/skills",
response_model=list[SkillResponse])

def get_all(
    id_jobPosting: int,
    db: Session = Depends(get_db),
): 
    skills = get_jobposting_skills(db, id_jobPosting)

    if skills is None: 
        raise HTTPException(
            status_code=404,
            detail="Job posting not found")

    return skills

@router.delete("/{id_jobPosting}/skills/{id_skill}")
def delete(
    id_jobPosting: int,
    id_skill: int,
    db: Session = Depends(get_db),
):

    deleted = delete_skill_jobposting(db, id_skill, id_jobPosting)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Job posting-skill association not found"
        )

    return {"message": "Job posting-skill association deleted successfully"}
