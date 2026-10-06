from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session 

from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.services.Ownership import require_company
from app.schemas.Location import LocationResponse
from app.services.CompanyLocation import (
    create_company_location,
    get_company_locations,
    delete_company_location,
)

router = APIRouter(
    prefix="/companies",
    tags=["Company Locations"],
)

@router.post("/{id_company}/locations/{id_location}")
def create(
    id_company: int,
    id_location: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    try:
        association, created = create_company_location(
            db,
            id_company,
            id_location,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    response.status_code = 201 if created else 200

    return {
        "id_company": association.id_company,
        "id_location": association.id_location,
        "created": created,
    }

@router.get("/{id_company}/locations", response_model= list[LocationResponse])
def get_all(
    id_company: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    locations = get_company_locations(db, id_company)

    if locations is None:
        raise HTTPException(status_code=404, detail="Company not found")

    return locations

@router.delete("/{id_company}/locations/{id_location}")
def delete (
    id_company: int,
    id_location: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)

    deleted = delete_company_location(db, id_company, id_location)

    if not deleted: 
        raise HTTPException(
            status_code = 404,
            detail="Company location association not found",
        )

    return {"message": "Company location association deleted successfully"}