from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Skill(Base):
    __tablename__="skills"

    id_skill: Mapped[int] = mapped_column(primary_key=True)
    name_skill: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
