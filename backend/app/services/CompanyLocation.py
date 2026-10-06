from sqlalchemy.orm import Session
from app.models.CompanyLocation import CompanyLocation
from app.models.Location import Location
from app.models.Company import Company

def create_company_location(
    db: Session,
    id_company: int,
    id_location:int,
) -> tuple[CompanyLocation, bool]:
    if db.get(Company, id_company) is None:
        raise LookupError("Company not found")

    if db.get(Location, id_location) is None:
        raise LookupError("Location not found")

    association = db.get(
        CompanyLocation,
        {
            "id_company": id_company,
            "id_location": id_location,
        },
    )

    if association is not None:
        return association, False

    association = CompanyLocation(
        id_company=id_company,
        id_location=id_location,
    )
    db.add(association)
    db.commit()
    db.refresh(association)

    return association, True

def get_company_locations(
    db: Session,
    id_company: int,
) -> list[Location] | None:
    if db.get(Company, id_company) is None:
        return None

    return (
        db.query(Location)
        .join(
            CompanyLocation,
            Location.id_location == CompanyLocation.id_location,
        )
        .filter(CompanyLocation.id_company == id_company)
        .all()
    )

def delete_company_location(
    db: Session,
    id_company: int,
    id_location: int,
) -> bool:
    association = db.get(
        CompanyLocation,
        {
            "id_company": id_company,
            "id_location": id_location,
        },
    )

    if association is None:
        return False

    db.delete(association)
    db.commit()

    return True 

