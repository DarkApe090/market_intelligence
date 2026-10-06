from sqlalchemy.orm import Session
from app.models.Location import Location
from app.models.JobPosting import JobPosting
from app.models.LocationJobPosting import LocationJobPosting

def create_location_jobposting(
    db: Session,
    id_jobPosting: int,
    id_location: int,
) -> tuple[LocationJobPosting, bool]:
    if db.get(JobPosting, id_jobPosting) is None:
        raise LookupError("Job posting not found")

    if db.get(Location, id_location) is None:
        raise LookupError("Location not found")

    association = db.get(
        LocationJobPosting,
        {
            "id_jobPosting": id_jobPosting,
            "id_location": id_location,
        },
    )

    if association is not None: 
        return association, False

    association = LocationJobPosting(
        id_jobPosting = id_jobPosting,
        id_location = id_location,
    )
    db.add(association)
    db.commit()
    db.refresh(association)

    return association, True

def get_jobposting_locations(
    db: Session,
    id_jobPosting: int,
) -> list[Location] | None:
    if db.get(JobPosting, id_jobPosting) is None: 
        return None

    return (
        db.query(Location)
        .join(
            LocationJobPosting,
            Location.id_location == LocationJobPosting.id_location,
        )
        .filter(LocationJobPosting.id_jobPosting == id_jobPosting)
        .all() 
    )

def delete_location_jobposting(
    db: Session,
    id_jobPosting: int,
    id_location: int,
) -> bool:
    association = db.get(
        LocationJobPosting,
        {
            "id_jobPosting": id_jobPosting,
            "id_location": id_location,
        },
    )

    if association is None: 
        return False

    db.delete(association)
    db.commit()

    return True