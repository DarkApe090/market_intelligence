from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.services.Ownership import require_company, require_contact
from app.services.GoogleMail import GoogleError
from app.schemas.Contact import (
    ApplyOutreachRequest,
    ApplyOutreachResponse,
    ContactReplyResponse,
    ContactResponse,
    OutreachContactResponse,
    OutreachStatusUpdate,
)
from app.services.CompanyContact import (
    apply_to_contact,
    create_company_contact,
    get_company_contacts,
    get_contact_reply,
    get_outreach_contacts,
    delete_company_contact,
    remove_company_from_outreach,
    sync_sent_replies,
    update_outreach_status,
)
from app.services.ContactEnrichment import enrich_company
from app.services.Quota import consume_quota

router = APIRouter (
    prefix="/companies",
    tags=["Company Contacts"],
)

@router.post("/{id_company}/contacts/{id_contact}")
def create(
    id_company: int,
    id_contact: int,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    contact = require_contact(db, id_contact, user)
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

    if created and not contact.email:
        background_tasks.add_task(enrich_company, id_company, contact.source_url, True)

    response.status_code = 201 if created else 200

    return {
        "id_company": association.id_company,
        "id_contact": association.id_contact,
        "created": created,
    }

@router.get("/outreach/contacts", response_model=list[OutreachContactResponse])
def get_outreach_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sync_sent_replies(db, user)
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

@router.post("/{id_company}/contacts/{id_contact}/apply", response_model=ApplyOutreachResponse)
def apply(
    id_company: int,
    id_contact: int,
    payload: ApplyOutreachRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    require_contact(db, id_contact, user)
    consume_quota(db, user, "send")
    try:
        return {"to": apply_to_contact(db, user, id_company, id_contact, payload.subject, payload.body)}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GoogleError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/{id_company}/contacts/{id_contact}/reply", response_model=ContactReplyResponse)
def get_reply(
    id_company: int,
    id_contact: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_company(db, id_company, user)
    require_contact(db, id_contact, user)
    try:
        reply = get_contact_reply(db, user, id_company, id_contact)
    except GoogleError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    if reply is None:
        raise HTTPException(status_code=404, detail="Ainda não há resposta neste Gmail.")
    return reply


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
