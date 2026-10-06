from sqlalchemy.orm import Session
from app.models.Contact import Contact
from app.schemas.Contact import CreateContact, UpdateContact
from app.models.User import User

def create_contact(db: Session, contact: CreateContact, user: User) -> Contact:
    db_contact = Contact(
        name_contact = contact.name_contact,
        role_contact = contact.role_contact,
        contact_type = contact.contact_type,
        cellphone = contact.cellphone,
        telephone = contact.telephone,
        email = contact.email,
        source_url = contact.source_url,
        id_user = user.id_user,
    )

    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)

    return db_contact

def get_contact(db: Session, id_contact: int, user: User) -> Contact | None:
    return db.query(Contact).filter(Contact.id_contact == id_contact, Contact.id_user == user.id_user).first()

def get_contacts(db: Session, user: User) -> list[Contact]:
    return db.query(Contact).filter(Contact.id_user == user.id_user).all()

def update_contact(
    db: Session,
    id_contact: int,
    contact: UpdateContact,
    user: User,
) -> Contact | None:

    db_contact = get_contact(db, id_contact, user)

    if db_contact is None: 
        return None

    for field, value in contact.model_dump(exclude_unset=True).items():
        setattr(db_contact, field, value)

    db.commit()
    db.refresh(db_contact)

    return db_contact

def delete_contact(db: Session , id_contact: int, user: User) -> bool:
    db_contact = get_contact(db, id_contact, user)

    if db_contact is None: 
        return False

    db.delete(db_contact)
    db.commit()

    return True




