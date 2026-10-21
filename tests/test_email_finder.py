from app.scrappers import email_finder
from app.scrappers.email_finder import classify_email, extract_emails, find_company_email, guess_website, pick_contact_email


def test_extract_emails_ignores_noise_and_reads_mailto():
    page = (
        '<a href="mailto:Careers@acme.com">x</a> info@acme.com logo@2x.png '
        "a@sentry.io noreply@acme.com"
    )

    assert extract_emails(page) == {"careers@acme.com", "info@acme.com"}
    assert extract_emails("join@acme.com dpo@acme.com privacy@acme.com") == {"join@acme.com"}
    assert extract_emails("sales@acme.com ventas@acme.com vendas@acme.com info@acme.com jobs@salesforce.com") == {
        "info@acme.com",
        "jobs@salesforce.com",
    }
    assert extract_emails("support@acme.com help@acme.com foxit@foxit.pt") == {"foxit@foxit.pt"}


def test_classify_email_prefers_known_prefixes_and_skips_personal_emails():
    assert classify_email("jobs@acme.com") == "careers"
    assert classify_email("contacto@acme.com") == "general"
    assert classify_email("contact@acme.com") == "general"
    assert classify_email("hi@acme.com") == "general"
    assert classify_email("joao.silva@acme.com") is None
    assert pick_contact_email({"contacto@acme.com", "jobs@acme.com"}) == "jobs@acme.com"
    assert pick_contact_email({"info@acme.com"}) == "info@acme.com"
    assert pick_contact_email({"joao.silva@acme.com"}) == "joao.silva@acme.com"
    assert pick_contact_email({"legal@dremio.com", "abuse@dremio.com"}) is None
    assert pick_contact_email({"legal@dremio.com", "hello@dremio.com"}) == "hello@dremio.com"
    assert pick_contact_email({"info@acme.com", "joao.silva@acme.com"}) == "info@acme.com"
    assert classify_email("recrutamento@acme.com") == "careers"
    assert classify_email("rh.porto@acme.com") == "careers"
    assert pick_contact_email({"rh.porto@acme.com"}) == "rh.porto@acme.com"
    assert classify_email("sayhello@wearemeta.io") == "general"
    assert pick_contact_email({"sales@acme.com", "vendas@acme.com"}) is None
    assert pick_contact_email({"sales@acme.com", "info@acme.com"}) == "info@acme.com"
    assert pick_contact_email({"support@foxitsoftware.com", "foxit@foxit.pt"}, "FOX IT") == "foxit@foxit.pt"
    assert pick_contact_email({"info@foxit.pt", "foxit@foxit.pt"}, "FOX IT") == "foxit@foxit.pt"


def test_find_company_email_follows_contact_links(monkeypatch):
    pages = {
        "https://acme.com/": '<a href="/carreira">Carreira</a>',
        "https://acme.com/carreira": "carreiras@acme.com",
    }
    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))

    assert find_company_email("https://acme.com", use_browser=False) == (
        "carreiras@acme.com",
        "careers",
        "https://acme.com/carreira",
    )


def test_find_company_email_prefers_careers_over_general(monkeypatch):
    pages = {
        "https://acme.com/": "info@acme.com",
        "https://acme.com/contact": "talent@acme.com",
    }
    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))

    assert find_company_email("acme.com") == (
        "talent@acme.com",
        "careers",
        "https://acme.com/contact",
    )


def test_same_company_domain_accepts_related_hostnames():
    assert email_finder._same_company_domain("info@dellentconsulting.com", "https://dellent.pt")
    assert email_finder._same_company_domain("jobs@acme.com", "https://www.acme.com")
    assert not email_finder._same_company_domain("hr@other.com", "https://acme.com")
    assert not email_finder._same_company_domain("support@foxitsoftware.com", "https://foxit.pt")
    assert not email_finder._same_company_domain("support@foxitsoftware.com", "https://foxit.com")


def test_emails_matching_company_keeps_the_brand_domain():
    page = "support@foxitsoftware.com foxit@foxit.pt info@other.com"
    assert email_finder.emails_matching_company(page, "FOX IT") == {"foxit@foxit.pt"}
    assert email_finder.emails_matching_company(
        "jobs@checkmarx.com hr@other.com",
        "Checkmarx Portugal",
    ) == {"jobs@checkmarx.com"}


def test_find_company_email_falls_back_to_general_and_ignores_other_domains(monkeypatch):
    pages = {
        "https://acme.com/": "hr@other.com hi@acme.com",
    }
    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))

    assert find_company_email("https://acme.com") == ("hi@acme.com", "general", "https://acme.com/")


def test_website_from_job_uses_company_domain_and_skips_boards():
    assert email_finder.website_from_job_url("https://acme.com/jobs/dev", "Acme") == "https://acme.com"
    assert email_finder.website_from_job_url("https://checkmarx.com/jobs/1", "Checkmarx Portugal") == "https://checkmarx.com"
    assert email_finder.website_from_job_url("https://www.itjobs.pt/oferta/1", "Acme") is None
    assert email_finder.website_from_job_url("https://www.net-empregos.com/1/net-developer/", "Acme") is None
    assert email_finder.website_from_job_url("https://pt.teamlyzer.com/companies/acme/job/1", "Acme") is None
    clickhouse_job = "https://www.arbeitnow.nl/jobs/companies/clickhouse/full-stack-software-engineer-226061"
    assert email_finder.website_from_job_url(clickhouse_job, "Clickhouse") is None
    assert email_finder.company_site("https://www.net-empregos.com") is None
    assert email_finder.company_site("wearemeta.io") == "https://wearemeta.io"
    page = '<a href="https://www.acme.com/careers">Acme</a><a href="https://linkedin.com/company/acme">LI</a>'
    assert email_finder.website_from_job_page(page, "https://weworkremotely.com/jobs/1", "Acme Lda") == "https://www.acme.com"


def test_guess_website_uses_first_domain_that_mentions_the_company(monkeypatch):
    pages = {
        "https://wearemeta.com": None,
        "https://wearemeta.io": "<title>We Are META</title>",
        "https://www.wearemeta.io": "<title>We Are META</title>",
    }
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))
    monkeypatch.setattr(email_finder, "DOMAIN_TLDS", ("com", "io"))

    assert guess_website("We are META") == "https://www.wearemeta.io"


def test_guess_website_prefers_country_tld_for_the_job_location(monkeypatch):
    pages = {
        "https://www.foxit.com": "Foxit Software foxit",
        "https://foxit.com": "Foxit Software foxit",
        "https://www.foxit.pt": "FOX IT foxit Portugal",
        "https://foxit.pt": "FOX IT foxit Portugal",
    }
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))
    monkeypatch.setattr(email_finder, "DOMAIN_TLDS", ("com", "pt"))

    assert guess_website("FOX IT", "Remote From Portugal") == "https://www.foxit.pt"


def test_find_company_email_respects_robots_txt(monkeypatch):
    from urllib.robotparser import RobotFileParser

    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /"])
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return "info@acme.com"

    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: robots)
    monkeypatch.setattr(email_finder, "fetch_page", fake_fetch)

    assert find_company_email("https://acme.com") is None
    assert fetched == []
