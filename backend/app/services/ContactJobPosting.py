from sqlalchemy.orm import Session
from app.models.Contact import Contact
from app.models.ContactJobPosting import ContactJobPosting
from app.models.JobPosting import JobPosting


def create_contact_jobposting(
    db: Session,
    id_jobPosting: int,
    id_contact: int, 
) -> tuple[ContactJobPosting, bool]:
    if db.get(JobPosting, id_jobPosting) is None:
        raise LookupError("Job posting not found")

    if db.get(Contact, id_contact) is None:
        raise LookupError("Contact not found")

    association = db.get(
        ContactJobPosting,
        {
            "id_jobPosting": id_jobPosting,
            "id_contact": id_contact,
        },
    )

    if association is not None:
        return association, False

    association = ContactJobPosting(
        id_jobPosting=id_jobPosting,
        id_contact=id_contact,
    )

    db.add(association)
    db.commit()
    db.refresh(association)

    return association, True

def get_jobposting_contacts(
    db: Session,
    id_jobPosting: int,
    id_user: int,
) -> list[Contact] | None:
    if db.get(JobPosting, id_jobPosting) is None:
        return None

    return (
        db.query(Contact)
        .join(
            ContactJobPosting,
            Contact.id_contact == ContactJobPosting.id_contact,
        )
        .filter(ContactJobPosting.id_jobPosting == id_jobPosting, Contact.id_user == id_user)
        .all()
    )

def delete_contact_jobposting(
    db: Session,
    id_jobPosting: int,
    id_contact: int,
) -> bool:
    association = db.get(
        ContactJobPosting,
        {
            "id_jobPosting": id_jobPosting,
            "id_contact": id_contact,
        },
    )

    if association is None: 
        return False

    db.delete(association)
    db.commit()

    return True