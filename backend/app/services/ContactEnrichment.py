from datetime import datetime, timedelta, timezone

from app.database.connection import SessionLocal
from app.models.Company import Company
from app.models.Contact import Contact
from app.models.ContactCompany import CompanyContact
from app.scrappers.email_finder import find_company_email, guess_website


RESEARCH_COOLDOWN = timedelta(days=7)


def enrich_company(id_company: int, website_url: str | None = None, force: bool = False) -> None:
    """Procura o email de contacto da empresa; corre em segundo plano com sessão própria."""
    db = SessionLocal()
    try:
        company = db.get(Company, id_company)
        if company is None:
            return

        now = datetime.now(timezone.utc)
        if not force and company.contact_searched_at and now - company.contact_searched_at < RESEARCH_COOLDOWN:
            return

        if website_url:
            company.website_url = website_url
        elif not company.website_url:
            company.website_url = guess_website(company.name_company)

        found = find_company_email(company.website_url) if company.website_url else None

        associations = (
            db.query(CompanyContact, Contact)
            .join(Contact, Contact.id_contact == CompanyContact.id_contact)
            .filter(CompanyContact.id_company == id_company, Contact.email.is_(None))
            .all()
        )
        for association, contact in associations:
            if found:
                email, email_type, page_url = found
                contact.email = email
                contact.contact_type = email_type
                contact.source_url = page_url
                if association.outreach_status == "no_email":
                    association.outreach_status = "to_contact"
            else:
                association.outreach_status = "no_email"

        company.contact_searched_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
