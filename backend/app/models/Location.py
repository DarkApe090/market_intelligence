from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Location(Base):
    __tablename__ = "locations"

    id_location: Mapped[int] = mapped_column(primary_key=True)
    street_name: Mapped[str] = mapped_column(String(250), nullable = False)
    zip_code: Mapped[str] = mapped_column(String(8), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    district: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parish: Mapped[str | None] = mapped_column(String(50), nullable=True)
    county: Mapped[str | None] = mapped_column(String(50), nullable=True)