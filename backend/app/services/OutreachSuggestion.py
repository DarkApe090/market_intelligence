from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.Company import Company
from app.models.Contact import Contact
from app.models.ContactCompany import CompanyContact
from app.models.ContactJobPosting import ContactJobPosting
from app.models.JobPosting import JobPosting
from app.models.Source import Source
from app.models.User import User
from app.models.UserJobPosting import UserJobPosting
from app.schemas.CareerProfile import SaveSuggestion
from app.scrappers.email_finder import classify_email, is_valid_email


def save_suggestion(db: Session, suggestion: SaveSuggestion, user: User) -> dict:
    """Guarda empresa, fonte, vaga e contacto de outreach numa única transação."""
    company_name = suggestion.company.strip()
    source_name = suggestion.source.strip()
    url = suggestion.url.strip()
    email = (suggestion.email or "").strip().casefold() or None
    if email and not is_valid_email(email):
        email = None

    try:
        company = (
            db.query(Company)
            .filter(Company.id_user == user.id_user, func.lower(Company.name_company) == company_name.casefold())
            .first()
        )
        company_created = company is None
        if company is None:
            company = Company(name_company=company_name, id_user=user.id_user)
            db.add(company)
            db.flush()

        source = (
            db.query(Source)
            .filter(func.lower(Source.name_source) == source_name.casefold())
            .first()
        )
        if source is None:
            source = Source(name_source=source_name)
            db.add(source)
            db.flush()

        jobposting = (
            db.query(JobPosting)
            .filter(JobPosting.id_source == source.id_source, JobPosting.url_jobPosting == url)
            .first()
        )
        if jobposting is None:
            jobposting = JobPosting(
                position_jobPosting=suggestion.title.strip(),
                id_source=source.id_source,
                url_jobPosting=url,
            )
            db.add(jobposting)
            db.flush()

        if db.get(UserJobPosting, {"id_user": user.id_user, "id_jobPosting": jobposting.id_jobPosting}) is None:
            db.add(UserJobPosting(id_user=user.id_user, id_jobPosting=jobposting.id_jobPosting, seen_at=None))

        contact = (
            db.query(Contact)
            .join(CompanyContact, CompanyContact.id_contact == Contact.id_contact)
            .filter(CompanyContact.id_company == company.id_company)
            .order_by(Contact.id_contact)
            .first()
        )
        already_in_outreach = contact is not None
        if contact is None:
            contact = Contact(
                contact_type=classify_email(email) if email else "careers",
                email=email,
                source_url=url,
                id_user=user.id_user,
            )
            db.add(contact)
            db.flush()
            db.add(CompanyContact(id_company=company.id_company, id_contact=contact.id_contact))
        elif email and not contact.email:
            contact.email = email
            contact.contact_type = classify_email(email) or contact.contact_type

        if db.get(ContactJobPosting, {"id_jobPosting": jobposting.id_jobPosting, "id_contact": contact.id_contact}) is None:
            db.add(ContactJobPosting(id_jobPosting=jobposting.id_jobPosting, id_contact=contact.id_contact))

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "id_company": company.id_company,
        "id_contact": contact.id_contact,
        "id_jobPosting": jobposting.id_jobPosting,
        "company_created": company_created,
        "already_in_outreach": already_in_outreach,
        "email": contact.email,
    }
