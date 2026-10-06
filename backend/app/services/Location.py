from sqlalchemy.orm import Session
from app.models.Location import Location
from app.schemas.Location import CreateLocation, UpdateLocation

def create_location(db: Session, location: CreateLocation) -> Location:
    
    db_location = Location(
        street_name=location.street_name,
        zip_code = location.zip_code,
        city = location.city,
        district = location.district,
        parish = location.parish,
        county = location.county
        )
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    
    return db_location

def get_location(db: Session, id_location: int) -> Location | None:
    return db.get(Location, id_location)

def get_locations(db: Session) -> list[Location]:
    return db.query(Location).all()

def update_location(db: Session, id_location: int, location: UpdateLocation) -> Location | None:

    db_location = db.get(Location, id_location)

    if db_location is None:
        return None
    if location.street_name is not None:
        db_location.street_name = location.street_name
    if location.zip_code is not None:
        db_location.zip_code = location.zip_code
    if location.city is not None: 
        db_location.city = location.city
    if location.district is not None:
        db_location.district = location.district
    if location.parish is not None:
        db_location.parish = location.parish
    if location.county is not None:
        db_location.county = location.county

    db.commit()
    db.refresh(db_location)

    return db_location

def delete_location(db: Session, id_location: int) -> bool:
    db_location = db.get(Location, id_location)

    if db_location is None: 
        return False

    db.delete(db_location)
    db.commit()

    return True
