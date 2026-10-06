from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class JobPosting(Base):
    __tablename__="jobpostings"
    __table_args__ = (
        UniqueConstraint(
            "id_source",
            "url_jobPosting",
            name="uq_jobpostings_source_url",
        ),
    )

    id_jobPosting: Mapped[int] = mapped_column(primary_key=True)
    position_jobPosting: Mapped[str] = mapped_column(String(250), nullable = False)
    id_source: Mapped[int] = mapped_column(ForeignKey("sources.id_source"), nullable = False)
    url_jobPosting: Mapped[str | None ] = mapped_column(String(1000), nullable=True)