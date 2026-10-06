from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.Company import Company
from app.models.Contact import Contact
from app.models.User import User


def require_company(db: Session, id_company: int, user: User) -> Company:
    company = db.get(Company, id_company)
    if company is None or company.id_user != user.id_user:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def require_contact(db: Session, id_contact: int, user: User) -> Contact:
    contact = db.get(Contact, id_contact)
    if contact is None or contact.id_user != user.id_user:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact
