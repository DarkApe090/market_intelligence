from app.models.Company import Company
from app.scrappers import job_sources
from app.services import ContactEnrichment


SUGGESTION = {
    "company": "Acme Lda",
    "title": "Software Engineer",
    "url": "https://example.com/job/1",
    "source": "Remote OK",
}


def test_save_suggestion_is_idempotent_and_links_outreach(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)

    first = client.post("/career-profile/suggestions/save", json=SUGGESTION)
    second = client.post("/career-profile/suggestions/save", json={**SUGGESTION, "company": "ACME LDA"})

    assert first.status_code == 200
    assert first.json()["company_created"] is True
    assert first.json()["already_in_outreach"] is False
    assert second.json()["company_created"] is False
    assert second.json()["already_in_outreach"] is True
    assert second.json()["id_jobPosting"] == first.json()["id_jobPosting"]
    assert len(client.get("/companies/outreach/contacts").json()) == 1
    assert len(client.get("/jobpostings/").json()) == 1


def test_find_email_rejects_ip_addresses(client):
    company = client.post("/companies/", json={"name_company": "Acme"}).json()

    response = client.post(
        f"/companies/{company['id_company']}/find-email",
        json={"website_url": "127.0.0.1"},
    )

    assert response.status_code == 422


def test_find_email_requires_existing_company(client):
    response = client.post("/companies/999/find-email", json={"website_url": "acme.com"})

    assert response.status_code == 404


def test_enrich_company_fills_email_and_marks_missing(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()

    session_factory = client.app.dependency_overrides
    db_generator = next(iter(session_factory.values()))()
    db = next(db_generator)
    monkeypatch.setattr(ContactEnrichment, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    monkeypatch.setattr(ContactEnrichment, "guess_website", lambda name: "https://acme.com")
    monkeypatch.setattr(
        ContactEnrichment,
        "find_company_email",
        lambda website: ("jobs@acme.com", "careers", "https://acme.com/careers"),
    )
    ContactEnrichment.enrich_company(saved["id_company"])

    contact = client.get("/companies/outreach/contacts").json()[0]
    assert contact["email"] == "jobs@acme.com"
    assert contact["contact_type"] == "careers"
    assert contact["website_url"] == "https://acme.com"
    assert db.get(Company, saved["id_company"]).contact_searched_at is not None

    monkeypatch.setattr(ContactEnrichment, "find_company_email", lambda website: None)
    other = client.post(
        "/career-profile/suggestions/save",
        json={**SUGGESTION, "company": "Beta", "url": "https://example.com/job/2"},
    ).json()
    ContactEnrichment.enrich_company(other["id_company"])

    statuses = {item["name_company"]: item["outreach_status"] for item in client.get("/companies/outreach/contacts").json()}
    assert statuses["Beta"] == "no_email"


def test_search_all_sources_tolerates_a_failing_source(monkeypatch):
    class Good:
        SOURCE_NAME = "Good"

        @staticmethod
        def search_jobs(tag, location, limit):
            return [{"company": "A", "title": "T", "url": "u"}]

    class Bad:
        SOURCE_NAME = "Bad"

        @staticmethod
        def search_jobs(tag, location, limit):
            raise RuntimeError("down")

    monkeypatch.setattr(job_sources, "JOB_SOURCES", (Good, Bad))

    jobs, failed = job_sources.search_all_sources("software", "Portugal", 5)

    assert len(jobs) == 1
    assert failed == ["Bad"]


def test_remove_company_from_outreach_cleans_related_rows(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()
    client.post(
        "/career-profile/suggestions/save",
        json={**SUGGESTION, "company": "Beta", "url": "https://example.com/job/2"},
    )

    response = client.delete(f"/companies/{saved['id_company']}/outreach")

    assert response.status_code == 200
    remaining = client.get("/companies/outreach/contacts").json()
    assert [item["name_company"] for item in remaining] == ["Beta"]
    assert client.get(f"/companies/{saved['id_company']}").status_code == 404
    assert client.get(f"/contacts/{saved['id_contact']}").status_code == 404

    again = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()
    assert again["company_created"] is True
    assert again["already_in_outreach"] is False


def test_remove_company_from_outreach_returns_404_for_unknown_company(client):
    assert client.delete("/companies/999/outreach").status_code == 404


def test_extract_emails_decodes_obfuscation():
    from app.scrappers.email_finder import extract_emails

    key = 0x42
    encoded = bytes([key]) + bytes(b ^ key for b in b"jobs@acme.com")
    page = f'<a data-cfemail="{encoded.hex()}"></a> hi [at] acme [dot] com mailto:team%40acme.com'
    assert extract_emails(page) == {"jobs@acme.com", "hi@acme.com", "team@acme.com"}


def test_browser_fallback_finds_js_rendered_email(monkeypatch):
    from app.scrappers import email_finder

    monkeypatch.setattr(email_finder, "fetch_page", lambda url: "<html></html>")
    monkeypatch.setattr(email_finder, "_allowed_by_robots", lambda website: None)
    monkeypatch.setattr(email_finder, "USE_BROWSER_FALLBACK", True)
    monkeypatch.setattr(
        email_finder, "render_pages", lambda urls: ["<a>careers@acme.com</a>"] + [None] * (len(urls) - 1)
    )

    found = email_finder.find_company_email("https://acme.com")
    assert found is not None and found[0] == "careers@acme.com"
