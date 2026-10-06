from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Contact(Base):
    __tablename__="contacts"

    id_contact: Mapped[int] = mapped_column(primary_key=True)
    name_contact: Mapped[str | None] = mapped_column(String(150))
    role_contact: Mapped[str | None] = mapped_column(String(150))
    contact_type: Mapped[str | None] = mapped_column(String(50))
    cellphone: Mapped[str | None] = mapped_column(String(20))
    telephone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    id_user: Mapped[int | None] = mapped_column(ForeignKey('users.id_user', ondelete='CASCADE'), nullable=True, index=True)
