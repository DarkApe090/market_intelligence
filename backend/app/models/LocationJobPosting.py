from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class LocationJobPosting(Base):
    __tablename__ = "location_job_postings"

    id_location: Mapped[int] = mapped_column(ForeignKey('locations.id_location'), primary_key=True)
    id_jobPosting: Mapped[int] = mapped_column(ForeignKey('jobpostings.id_jobPosting'), primary_key=True)
