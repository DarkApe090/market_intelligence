from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class ContactJobPosting(Base):
    __tablename__="contact_job_postings"

    id_jobPosting: Mapped[int] = mapped_column(ForeignKey('jobpostings.id_jobPosting'), primary_key=True)
    id_contact: Mapped[int] = mapped_column(ForeignKey('contacts.id_contact'), primary_key=True)
