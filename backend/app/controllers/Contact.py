from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.User import User
from app.services.Auth import get_current_user
from app.schemas.Contact import (CreateContact, UpdateContact, ContactResponse)
from app.services.Contact import (create_contact, get_contact, get_contacts, update_contact, delete_contact)

router = APIRouter(
    prefix = "/contacts",
    tags= ["Contacts"]
)

@router.post("/", response_model= ContactResponse)
def create(contact: CreateContact, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    return create_contact(db, contact, user)

@router.get("/{id_contact}", response_model = ContactResponse)
def get(id_contact: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    contact = get_contact(db, id_contact, user)

    if contact is None:
        raise HTTPException(
            status_code = 404,
            detail = "Contact not found"
        )
    
    return contact

@router.get("/", response_model= list[ContactResponse])
def get_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    return get_contacts(db, user)

@router.put("/{id_contact}", response_model = ContactResponse)
def update(
    id_contact: int,
    contact: UpdateContact,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    updated_contact = update_contact(
        db,
        id_contact,
        contact,
        user,
    )

    if updated_contact is None:
        raise HTTPException(
            status_code= 404,
            detail = "Contact not found"
        )

    return updated_contact

@router.delete("/{id_contact}")
def delete(id_contact: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):

    deleted = delete_contact(db, id_contact, user)

    if not deleted:
        raise HTTPException(
            status_code = 404,
            detail ="Contact not found"
        )

    return {"message": "Contact deleted successfully"}