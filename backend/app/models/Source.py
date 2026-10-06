from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Source(Base):
    __tablename__="sources"

    id_source: Mapped[int] = mapped_column(primary_key=True)
    name_source: Mapped[str] = mapped_column(String(250), nullable=False)
    id_location: Mapped[int | None] = mapped_column(ForeignKey('locations.id_location'), nullable=True)
