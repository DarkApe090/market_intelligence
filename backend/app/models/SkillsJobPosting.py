from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class SkillJobPosting(Base):
    __tablename__ = "skill_job_postings"

    id_skill: Mapped[int] = mapped_column(ForeignKey('skills.id_skill'), primary_key=True)
    id_jobPosting: Mapped[int] = mapped_column(ForeignKey('jobpostings.id_jobPosting'), primary_key=True)