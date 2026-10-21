import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.Company import Company
from app.models.CompanyLocation import CompanyLocation
from app.models.Contact import Contact
from app.models.ContactCompany import CompanyContact
from app.models.ContactJobPosting import ContactJobPosting
from app.models.JobPosting import JobPosting
from app.models.User import GoogleAccount, User
from app.models.UserJobPosting import UserJobPosting
from app.services.GoogleMail import GoogleError, fetch_reply, find_sent_message, has_reply, send_email, status_for_reply

logger = logging.getLogger(__name__)

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

    user_jobs: dict[int, tuple[int, object]] = {}
    for id_contact, id_job, seen_at in (
        db.query(ContactJobPosting.id_contact, UserJobPosting.id_jobPosting, UserJobPosting.seen_at)
        .join(UserJobPosting, UserJobPosting.id_jobPosting == ContactJobPosting.id_jobPosting)
        .filter(UserJobPosting.id_user == id_user)
        .order_by(UserJobPosting.id_jobPosting)
        .all()
    ):
        user_jobs[id_contact] = (id_job, seen_at)

    return [
        {
            "outreach_status": association.outreach_status,
            "sent_at": association.sent_at,
            "id_company": company.id_company,
            "name_company": company.name_company,
            "website_url": company.website_url,
            "job_title": job_titles.get(contact.id_contact),
            "id_jobPosting": (user_jobs.get(contact.id_contact) or (None, None))[0],
            "job_seen_at": (user_jobs.get(contact.id_contact) or (None, None))[1],
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


def apply_to_contact(
    db: Session,
    user: User,
    id_company: int,
    id_contact: int,
    subject: str,
    body: str,
) -> str:
    """Envia pelo Gmail o email que o utilizador reviu e marca a candidatura como enviada."""
    association = db.get(CompanyContact, {"id_company": id_company, "id_contact": id_contact})
    contact = db.get(Contact, id_contact)
    if association is None or contact is None:
        raise LookupError("Company-contact association not found")
    if not contact.email:
        raise ValueError("Esta empresa ainda não tem email.")
    if association.outreach_status == "rejected":
        raise ValueError("Esta candidatura não foi selecionada.")

    association.gmail_thread_id = send_email(db, user, contact.email, subject, body, True)
    association.sent_at = datetime.now(timezone.utc)
    association.outreach_status = "sent"
    db.commit()
    return contact.email


def sync_sent_replies(db: Session, user: User) -> None:
    account = db.get(GoogleAccount, user.id_user)
    if account is None:
        return
    rows = (
        db.query(CompanyContact, Contact)
        .join(Company, Company.id_company == CompanyContact.id_company)
        .join(Contact, Contact.id_contact == CompanyContact.id_contact)
        .filter(Company.id_user == user.id_user, CompanyContact.outreach_status == "sent")
        .all()
    )
    if not rows:
        return
    try:
        changed = False
        for association, contact in rows:
            if association.sent_at is None and contact.email:
                sent = find_sent_message(account, contact.email)
                if sent:
                    association.gmail_thread_id = association.gmail_thread_id or sent[0]
                    association.sent_at = sent[1]
                    changed = True
            if has_reply(account, association.gmail_thread_id, contact.email, association.sent_at):
                association.outreach_status = status_for_reply(
                    fetch_reply(account, association.gmail_thread_id, contact.email, association.sent_at)
                )
                changed = True
        if changed:
            db.commit()
    except GoogleError as error:
        db.rollback()
        logger.warning("Gmail reply sync skipped: %s", error)


def get_contact_reply(db: Session, user: User, id_company: int, id_contact: int) -> dict | None:
    account = db.get(GoogleAccount, user.id_user)
    association = db.get(CompanyContact, {"id_company": id_company, "id_contact": id_contact})
    contact = db.get(Contact, id_contact)
    if account is None or association is None or contact is None:
        return None
    reply = fetch_reply(account, association.gmail_thread_id, contact.email, association.sent_at)
    if reply is None:
        return None
    if association.outreach_status == "replied" and status_for_reply(reply) == "rejected":
        association.outreach_status = "rejected"
        db.commit()
    return {**reply, "outreach_status": association.outreach_status}


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
