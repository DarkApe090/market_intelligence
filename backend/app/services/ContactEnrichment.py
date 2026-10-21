from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.Company import Company
from app.models.Contact import Contact
from app.models.ContactCompany import CompanyContact
from app.models.ContactJobPosting import ContactJobPosting
from app.models.JobPosting import JobPosting
from app.scrappers import email_finder
from app.scrappers.email_finder import classify_email, find_company_email, guess_website, is_valid_email


RESEARCH_COOLDOWN = timedelta(days=7)


def fill_job_page_emails(suggestions: list[dict]) -> None:
    """Lê o anúncio; a procura no site da empresa fica para quando a vaga é guardada."""
    missing = [item for item in suggestions if not item.get("email")]
    if not missing:
        return

    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = list(pool.map(lambda item: email_finder.fetch_page(item["url"]), missing))
    for item, page in zip(missing, pages):
        if not page:
            continue
        email = email_finder.pick_contact_email(
            email_finder.emails_matching_company(page, item["company"]),
            item["company"],
        )
        if email:
            item["email"] = email


def fill_suggestion_emails(suggestions: list[dict]) -> None:
    """Email da vaga primeiro; se faltar, contactos da empresa e, por último, o geral."""
    fill_job_page_emails(suggestions)
    still_missing = [item for item in suggestions if not item.get("email")]
    companies = list(dict.fromkeys(item["company"] for item in still_missing))
    if not companies:
        return

    def lookup(name: str) -> str | None:
        place = next((item.get("location") for item in still_missing if item["company"] == name), None)
        website = email_finder.guess_website(name, place)
        if not website:
            return None
        found = email_finder.find_company_email(website, use_browser=False)
        return found[0] if found else None

    with ThreadPoolExecutor(max_workers=4) as pool:
        found_by_company = dict(zip(companies, pool.map(lookup, companies)))
    for item in still_missing:
        item["email"] = found_by_company.get(item["company"])


def _company_jobs(db: Session, id_company: int) -> list[str]:
    rows = (
        db.query(JobPosting.url_jobPosting, Contact.source_url)
        .select_from(CompanyContact)
        .join(Contact, Contact.id_contact == CompanyContact.id_contact)
        .outerjoin(ContactJobPosting, ContactJobPosting.id_contact == Contact.id_contact)
        .outerjoin(JobPosting, JobPosting.id_jobPosting == ContactJobPosting.id_jobPosting)
        .filter(CompanyContact.id_company == id_company)
        .all()
    )
    urls: list[str] = []
    for job_url, source_url in rows:
        for url in (job_url, source_url):
            if url and url not in urls:
                urls.append(url)
    return urls


def _job_listings(db: Session, id_company: int) -> list[tuple[str, str | None]]:
    return [(url, email_finder.fetch_page(url)) for url in _company_jobs(db, id_company)]


def _email_from_job_listings(
    listings: list[tuple[str, str | None]],
    company_name: str,
) -> tuple[str, str, str] | None:
    """Email do domínio da empresa, mesmo que o anúncio esteja num job board."""
    for url, page in listings:
        if not page:
            continue
        picked = email_finder.pick_contact_email(
            email_finder.emails_matching_company(page, company_name),
            company_name,
        )
        if picked:
            return picked, classify_email(picked) or "careers", url
    return None


def _discover_website(
    company: Company,
    website_url: str | None,
    listings: list[tuple[str, str | None]],
    location: str | None,
    reuse_stored: bool,
) -> str | None:
    """Site da empresa: o indicado, o da vaga, ou o adivinhado pelo nome."""
    found = email_finder.company_site(website_url)
    if found:
        return found
    if reuse_stored:
        found = email_finder.company_site(company.website_url)
        if found:
            return found
    for url, page in listings:
        found = email_finder.website_from_job_url(url, company.name_company)
        if found:
            return found
        if page:
            found = email_finder.website_from_job_page(page, url, company.name_company)
            if found:
                return found
    return guess_website(company.name_company, location)


def save_company_email(db: Session, id_company: int, email: str) -> None:
    """Guarda o email indicado pelo utilizador nos contactos da empresa."""
    email = email.strip().casefold()
    if not is_valid_email(email):
        raise ValueError("Este email não serve para candidaturas.")
    associations = (
        db.query(CompanyContact, Contact)
        .join(Contact, Contact.id_contact == CompanyContact.id_contact)
        .filter(CompanyContact.id_company == id_company)
        .all()
    )
    email_type = classify_email(email)
    for association, contact in associations:
        contact.email = email
        if email_type:
            contact.contact_type = email_type
        if association.outreach_status == "no_email":
            association.outreach_status = "to_contact"
    db.commit()


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

        listings = _job_listings(db, company.id_company)
        company.website_url = _discover_website(
            company, website_url, listings, None, reuse_stored=not force,
        )
        found = _email_from_job_listings(listings, company.name_company)
        if found is None and company.website_url:
            found = find_company_email(company.website_url)

        associations = (
            db.query(CompanyContact, Contact)
            .join(Contact, Contact.id_contact == CompanyContact.id_contact)
            .filter(CompanyContact.id_company == id_company)
            .all()
        )
        for association, contact in associations:
            if contact.email and is_valid_email(contact.email):
                continue
            if found:
                email, email_type, page_url = found
                contact.email = email
                contact.contact_type = email_type
                contact.source_url = page_url
                if association.outreach_status == "no_email":
                    association.outreach_status = "to_contact"
            elif not contact.email or not is_valid_email(contact.email):
                contact.email = None
                association.outreach_status = "no_email"

        company.contact_searched_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
