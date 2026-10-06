from sqlalchemy.orm import Session
from app.models.JobPosting import JobPosting
from app.models.Skills import Skill
from app.models.SkillsJobPosting import SkillJobPosting


def create_skill_jobposting(
    db: Session,
    id_skill: int,
    id_jobPosting: int,
) -> tuple[SkillJobPosting, bool]:

    if db.get(Skill, id_skill) is None:
        raise LookupError("Skill not found")
    
    if db.get(JobPosting, id_jobPosting) is None:
        raise LookupError("Job posting not found")

    association = db.get(
        SkillJobPosting,
        {
            "id_skill": id_skill,
            "id_jobPosting": id_jobPosting,
        },
    )

    if association is not None:
        return association, False

    association = SkillJobPosting(
        id_skill = id_skill,
        id_jobPosting = id_jobPosting,
    )

    db.add(association)
    db.commit()
    db.refresh(association)

    return association, True

def get_jobposting_skills(
    db: Session,
    id_jobPosting: int,
) -> list[Skill] | None: 

    if db.get(JobPosting, id_jobPosting) is None:
        return None

    return (
        db.query(Skill)
        .join(
            SkillJobPosting,
            Skill.id_skill == SkillJobPosting.id_skill,
        )
        .filter(SkillJobPosting.id_jobPosting == id_jobPosting)
        .all()
    )

def delete_skill_jobposting(
    db: Session,
    id_skill: int,
    id_jobPosting: int,
) -> bool:

    association = db.get(
        SkillJobPosting,
        {
            "id_skill": id_skill,
            "id_jobPosting": id_jobPosting,
        },
    )

    if association is None:
        return False

    db.delete(association)
    db.commit()

    return True