from sqlalchemy.orm import Session

from app.models.Skills import Skill
from app.schemas.Skills import CreateSkill, UpdateSkill


def create_skill(
    db: Session,
    skill: CreateSkill
) -> Skill:

    db_skill = Skill(
        name_skill=skill.name_skill
    )

    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)

    return db_skill


def get_skill(
    db: Session,
    id_skill: int
) -> Skill | None:

    return db.query(Skill).filter(
        Skill.id_skill == id_skill
    ).first()


def get_skills(
    db: Session
) -> list[Skill]:

    return db.query(Skill).all()


def update_skill(
    db: Session,
    id_skill: int,
    skill: UpdateSkill
) -> Skill | None:

    db_skill = db.get(Skill, id_skill)

    if db_skill is None:
        return None

    db_skill.name_skill = skill.name_skill

    db.commit()
    db.refresh(db_skill)

    return db_skill


def delete_skill(
    db: Session,
    id_skill: int
) -> bool:

    db_skill = db.get(Skill, id_skill)

    if db_skill is None:
        return False

    db.delete(db_skill)
    db.commit()

    return True