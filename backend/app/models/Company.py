from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Company(Base):
    __tablename__ = "companies"

    id_company: Mapped[int] = mapped_column(primary_key=True)
    name_company: Mapped[str] = mapped_column(String(150), nullable = False)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable = True)
    contact_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable = True)
    id_user: Mapped[int | None] = mapped_column(ForeignKey('users.id_user', ondelete='CASCADE'), nullable = True, index = True)
