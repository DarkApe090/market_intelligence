from app.scrappers import email_finder
from app.scrappers.email_finder import classify_email, extract_emails, find_company_email


def test_extract_emails_ignores_noise_and_reads_mailto():
    page = (
        '<a href="mailto:Careers@acme.com">x</a> info@acme.com logo@2x.png '
        "a@sentry.io noreply@acme.com"
    )

    assert extract_emails(page) == {"careers@acme.com", "info@acme.com"}


def test_classify_email_prefers_known_prefixes_and_skips_personal_emails():
    assert classify_email("jobs@acme.com") == "careers"
    assert classify_email("hi@acme.com") == "general"
    assert classify_email("joao.silva@acme.com") is None


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


def test_find_company_email_falls_back_to_general_and_ignores_other_domains(monkeypatch):
    pages = {
        "https://acme.com/": "hr@other.com hi@acme.com",
    }
    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))

    assert find_company_email("https://acme.com") == ("hi@acme.com", "general", "https://acme.com/")


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
