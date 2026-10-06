from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.Location import (CreateLocation, UpdateLocation, LocationResponse)
from app.services.Location import (create_location, get_location, get_locations, update_location, delete_location)


router = APIRouter(
    prefix = "/locations",
    tags = ["Locations"]
)

@router.post("/", response_model=LocationResponse)
def create(location: CreateLocation, db: Session = Depends(get_db)):
    return create_location(db, location)

@router.get("/{id_location}", response_model = LocationResponse)
def get(id_location: int, db: Session = Depends(get_db)):

    location = get_location(db, id_location)

    if location is None:
        raise HTTPException(
            status_code= 404,
            detail = "Location not found"
        )

    return location

@router.get("/", response_model=list[LocationResponse])
def get_all(db: Session = Depends(get_db)):

    return get_locations(db)

@router.put("/{id_location}", response_model= LocationResponse)
def update(
    id_location: int,
    location: UpdateLocation,
    db: Session = Depends(get_db)
): 

    updated_location = update_location(
        db,
        id_location,
        location
    )

    if updated_location is None:
        raise HTTPException(
            status_code=404,
            detail = "Location not found"
        )

    return updated_location
    

@router.delete("/{id_location}")
def delete(id_location: int, db: Session = Depends(get_db)):

    deleted = delete_location(db, id_location)

    if not deleted:
        raise HTTPException(
            status_code = 404,
            detail = "Location not found"
        )

    return {"message": "Location deleted successfully"}