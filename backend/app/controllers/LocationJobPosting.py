from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.Location import LocationResponse
from app.services.LocationJobPosting import (
    create_location_jobposting,
    get_jobposting_locations,
    delete_location_jobposting,
)

router = APIRouter(
    prefix="/jobpostings",
    tags=["Job Posting Locations"],
)

@router.post("/{id_jobPosting}/locations/{id_location}")
def create(
    id_jobPosting: int,
    id_location: int,
    response: Response,
    db: Session = Depends(get_db)
):

    try:
        association, created = create_location_jobposting(
            db, 
            id_jobPosting,
            id_location,
        )

    except LookupError as error:
        raise HTTPException (
            status_code=404,
            detail=str(error))

    response.status_code = 201 if created else 200

    return {
        "id_jobPosting": association.id_jobPosting,
        "id_location": association.id_location,
        "created": created,
    }

@router.get("/{id_jobPosting}/locations", response_model=list[LocationResponse])
def get_all(
    id_jobPosting: int,
    db: Session = Depends(get_db),
):
    locations = get_jobposting_locations(db, id_jobPosting)

    if locations is None:
        raise HTTPException(
            status_code = 404,
            detail="Job posting not found"
        )

    return locations

@router.delete("/{id_jobPosting}/locations/{id_location}")
def delete(
    id_jobPosting: int,
    id_location: int,
    db: Session = Depends(get_db),
):
    deleted = delete_location_jobposting(db, id_jobPosting, id_location)

    if not deleted: 
        raise HTTPException(
            status_code=404,
            detail="Job posting-location association not found",
        )

    return {"message": "Job posting-location association deleted successfully"}