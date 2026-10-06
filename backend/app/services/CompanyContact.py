from sqlalchemy.orm import Session
from app.models.Company import Company
from app.models.CompanyLocation import CompanyLocation
from app.models.Contact import Contact
from app.models.ContactCompany import CompanyContact 
from app.models.ContactJobPosting import ContactJobPosting
from app.models.JobPosting import JobPosting

def create_company_contact(
    db: Session,
    id_company: int,
    id_contact: int,
) -> tuple[CompanyContact, bool]:
    if db.get(Company, id_company) is None: 
        raise LookupError("Company not found")

    if db.get(Contact, id_contact) is None:
        raise LookupError("Contact not found")

    association = db.get(
        CompanyContact,
        {
            "id_company": id_company,
            "id_contact": id_contact,
        },
    )

    if association is not None:
        return association, False

    association = CompanyContact(
        id_company = id_company,
        id_contact = id_contact,
    )
    db.add(association)
    db.commit()
    db.refresh(association)

    return association, True


def get_company_contacts(
    db: Session, 
    id_company: int,
) -> list[Contact] | None:
    if db.get(Company, id_company) is None:
        return None

    return (
        db.query(Contact)
        .join(
            CompanyContact,
            Contact.id_contact == CompanyContact.id_contact,
        )
        .filter(CompanyContact.id_company == id_company)
        .all()
    )


def get_outreach_contacts(db: Session, id_user: int) -> list[dict]:
    rows = (
        db.query(CompanyContact, Company, Contact)
        .join(Company, Company.id_company == CompanyContact.id_company)
        .join(Contact, Contact.id_contact == CompanyContact.id_contact)
        .filter(Company.id_user == id_user)
        .order_by(Company.name_company, Contact.name_contact, Contact.email)
        .all()
    )

    job_titles: dict[int, str] = {}
    for id_contact, title in (
        db.query(ContactJobPosting.id_contact, JobPosting.position_jobPosting)
        .join(JobPosting, JobPosting.id_jobPosting == ContactJobPosting.id_jobPosting)
        .order_by(JobPosting.id_jobPosting)
        .all()
    ):
        job_titles[id_contact] = title

    return [
        {
            "outreach_status": association.outreach_status,
            "id_company": company.id_company,
            "name_company": company.name_company,
            "website_url": company.website_url,
            "job_title": job_titles.get(contact.id_contact),
            "id_contact": contact.id_contact,
            "name_contact": contact.name_contact,
            "role_contact": contact.role_contact,
            "contact_type": contact.contact_type,
            "cellphone": contact.cellphone,
            "telephone": contact.telephone,
            "email": contact.email,
            "source_url": contact.source_url,
        }
        for association, company, contact in rows
    ]


def update_outreach_status(
    db: Session,
    id_company: int,
    id_contact: int,
    outreach_status: str,
) -> CompanyContact | None:
    association = db.get(
        CompanyContact,
        {"id_company": id_company, "id_contact": id_contact},
    )

    if association is None:
        return None

    association.outreach_status = outreach_status
    db.commit()
    db.refresh(association)
    return association


def delete_company_contact(
    db: Session,
    id_company: int,
    id_contact: int,
) -> bool:
    association = db.get(
        CompanyContact,
        {
            "id_company": id_company,
            "id_contact": id_contact,
        },
    )

    if association is None: 
        return False

    db.delete(association)
    db.commit()

    return True

def remove_company_from_outreach(db: Session, id_company: int) -> bool:
    """Retira a empresa da lista de prospe??o e apaga os contactos que ficam sem empresa."""
    company = db.get(Company, id_company)
    if company is None:
        return False

    try:
        contact_ids = [
            row.id_contact
            for row in db.query(CompanyContact.id_contact)
            .filter(CompanyContact.id_company == id_company)
            .all()
        ]
        db.query(CompanyContact).filter(CompanyContact.id_company == id_company).delete()

        for id_contact in contact_ids:
            still_linked = (
                db.query(CompanyContact)
                .filter(CompanyContact.id_contact == id_contact)
                .first()
            )
            if still_linked is None:
                db.query(ContactJobPosting).filter(ContactJobPosting.id_contact == id_contact).delete()
                db.query(Contact).filter(Contact.id_contact == id_contact).delete()

        has_location = (
            db.query(CompanyLocation)
            .filter(CompanyLocation.id_company == id_company)
            .first()
        )
        if has_location is None:
            db.delete(company)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return True
