from datetime import datetime 
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class UserJobPosting(Base):
    __tablename__="user_jobpostings"

    id_user: Mapped[int] = mapped_column(
        ForeignKey("users.id_user"),
        primary_key=True,
    )

    id_jobPosting: Mapped[int] = mapped_column(
        ForeignKey("jobpostings.id_jobPosting"),
        primary_key=True,
    )

    seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )