from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.services.Ownership import require_company, require_contact
from app.schemas.Contact import (
    ContactResponse,
    OutreachContactResponse,
    OutreachStatusUpdate,
)
from app.services.CompanyContact import (
    create_company_contact,
    get_company_contacts,
    get_outreach_contacts,
    delete_company_contact,
    remove_company_from_outreach,
    update_outreach_status,
)

router = APIRouter (
    prefix="/companies",
    tags=["Company Contacts"],
)

@router.post("/{id_company}/contacts/{id_contact}")
def create(
    id_company: int,
    id_contact: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    require_contact(db, id_contact, user)
    try:
        association, created = create_company_contact(
            db,
            id_company,
            id_contact,
        )
    except LookupError as error:
        raise HTTPException (
            status_code = 404,
            detail= str(error)
        )

    response.status_code = 201 if created else 200

    return {
        "id_company": association.id_company,
        "id_contact": association.id_contact,
        "created": created,
    }

@router.get("/outreach/contacts", response_model=list[OutreachContactResponse])
def get_outreach_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_outreach_contacts(db, user.id_user)

@router.get("/{id_company}/contacts", response_model=list[ContactResponse])
def get_all(
    id_company: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    contacts = get_company_contacts(db, id_company)

    if contacts is None: 
        raise HTTPException(
            status_code=404,
            detail = "Company not found"
        )

    return contacts

@router.patch("/{id_company}/contacts/{id_contact}/status")
def update_status(
    id_company: int,
    id_contact: int,
    update: OutreachStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    require_contact(db, id_contact, user)
    association = update_outreach_status(
        db,
        id_company,
        id_contact,
        update.outreach_status,
    )

    if association is None:
        raise HTTPException(
            status_code=404,
            detail="Company-contact association not found",
        )

    return {
        "id_company": association.id_company,
        "id_contact": association.id_contact,
        "outreach_status": association.outreach_status,
    }

@router.delete("/{id_company}/outreach")
def remove_from_outreach(
    id_company: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    if not remove_company_from_outreach(db, id_company):
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return {"message": "Company removed from outreach list"}

@router.delete("/{id_company}/contacts/{id_contact}")
def delete(
    id_company: int,
    id_contact: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    require_contact(db, id_contact, user)

    deleted = delete_company_contact(db, id_company, id_contact)

    if not deleted:
        raise HTTPException(
            status_code = 404,
            detail = "Company-contact association not found"
        )

    return {"message": "Company-contact association deleted successfully"}
