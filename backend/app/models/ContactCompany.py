from datetime import datetime

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class CompanyContact(Base):
    __tablename__="company_contacts"

    id_company: Mapped[int] = mapped_column(ForeignKey('companies.id_company'), primary_key=True)
    id_contact: Mapped[int] = mapped_column(ForeignKey('contacts.id_contact'), primary_key=True)
    outreach_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="to_contact",
    )
    gmail_thread_id: Mapped[str | None] = mapped_column(String(128))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
