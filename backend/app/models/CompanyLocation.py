from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.Location import Location  # noqa: F401

class CompanyLocation(Base):
    __tablename__="company_locations"

    id_company: Mapped[int] = mapped_column(ForeignKey('companies.id_company'), primary_key=True)
    id_location: Mapped[int] = mapped_column(ForeignKey('locations.id_location'), primary_key=True)