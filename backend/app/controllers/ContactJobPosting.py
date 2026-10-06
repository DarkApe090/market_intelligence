from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.services.Ownership import require_contact
from app.schemas.Contact import ContactResponse
from app.services.ContactJobPosting import (
    create_contact_jobposting,
    get_jobposting_contacts,
    delete_contact_jobposting,
)

router = APIRouter(
    prefix="/jobpostings",
    tags=["Job Posting Contacts"],
)


@router.post("/{id_jobPosting}/contacts/{id_contact}")
def create(
    id_jobPosting: int,
    id_contact: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_contact(db, id_contact, user)
    try:
        association, created = create_contact_jobposting(
            db,
            id_jobPosting,
            id_contact,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error))

    response.status_code = 201 if created else 200

    return {
        "id_jobPosting": association.id_jobPosting,
        "id_contact": association.id_contact,
        "created": created,
    }


@router.get("/{id_jobPosting}/Contacts", response_model=list[ContactResponse])
def get_all(
    id_jobPosting: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contacts = get_jobposting_contacts(db, id_jobPosting, user.id_user)

    if contacts is None:
        raise HTTPException(status_code=404,detail="Job posting-contact association not found")

    return {
        "message": "Job posting-contact association deleted successfully"}