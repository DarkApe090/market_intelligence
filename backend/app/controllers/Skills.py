from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session 
from app.database.connection import get_db
from app.schemas.Skills import ( CreateSkill, UpdateSkill, SkillResponse)
from app.services.Skills import ( create_skill, get_skill, get_skills, update_skill, delete_skill)

router = APIRouter(
    prefix="/skills",
    tags = ["Skills"]
)

@router.post("/", response_model= SkillResponse)
def create(skill: CreateSkill, db: Session = Depends(get_db)):
    return create_skill(db, skill)

@router.get("/{id_skill}", response_model= SkillResponse)
def get(id_skill: int, db: Session = Depends(get_db)):

    skill = get_skill(db, id_skill)

    if skill is None:
        raise HTTPException(
            status_code=404,
            detail="Skill not found"
        )

    return skill

@router.get("/", response_model=list[SkillResponse])
def get_all (db: Session = Depends(get_db)):
    return get_skills(db)

@router.put("/{id_skill}", response_model=SkillResponse)
def update(
    id_skill: int, 
    skill: UpdateSkill,
    db: Session = Depends(get_db)
): 

    updated_skill = update_skill(
        db,
        id_skill,
        skill
    )

    if updated_skill is None:
        raise HTTPException(
            status_code=404,
            detail = "Skill not found"
        )

    return updated_skill

@router.delete("/{id_skill}")
def delete(id_skill: int, db: Session = Depends(get_db)):

    deleted = delete_skill(db, id_skill)

    if not deleted:
        raise HTTPException(
            status_code= 404,
            detail = "Skill not found"
        )

    return {"message": "Skill deleted successfully"}