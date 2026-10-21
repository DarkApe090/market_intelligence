from app.models.Company import Company
from app.scrappers import email_finder
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
    linked = client.get("/user-jobpostings/").json()
    assert len(linked) == 1
    assert linked[0]["id_jobPosting"] == first.json()["id_jobPosting"]
    assert linked[0]["seen_at"] is None
    outreach = client.get("/companies/outreach/contacts").json()[0]
    assert outreach["id_jobPosting"] == first.json()["id_jobPosting"]
    assert outreach["job_title"] == "Software Engineer"
    assert outreach["job_seen_at"] is None


def test_save_without_email_starts_async_enrich(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.controllers.CareerProfile.enrich_company",
        lambda id_company, website_url=None, force=False: calls.append((id_company, force)),
    )
    saved = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()
    assert calls == [(saved["id_company"], True)]

    client.post("/career-profile/suggestions/save", json={**SUGGESTION, "title": "Outra vaga", "url": "https://example.com/job/2"})
    assert calls == [(saved["id_company"], True)]


def test_save_suggestion_drops_sales_email(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post(
        "/career-profile/suggestions/save",
        json={**SUGGESTION, "email": "sales@acme.com"},
    ).json()
    assert saved["email"] is None
    assert client.get("/companies/outreach/contacts").json()[0]["email"] is None


def test_save_with_email_skips_enrich(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.controllers.CareerProfile.enrich_company",
        lambda *args, **kwargs: calls.append(args),
    )
    client.post("/career-profile/suggestions/save", json={**SUGGESTION, "email": "jobs@acme.com"})
    assert calls == []


def test_new_contact_without_email_starts_async_enrich(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.controllers.CompanyContact.enrich_company",
        lambda id_company, website_url=None, force=False: calls.append((id_company, website_url, force)),
    )
    company = client.post("/companies/", json={"name_company": "Acme"}).json()
    contact = client.post("/contacts/", json={
        "name_contact": None,
        "role_contact": None,
        "contact_type": "careers",
        "email": None,
        "source_url": "https://acme.com",
    }).json()
    response = client.post(f"/companies/{company['id_company']}/contacts/{contact['id_contact']}")
    assert response.status_code == 201
    assert calls == [(company["id_company"], "https://acme.com", True)]


def test_save_suggestion_links_the_same_job_to_each_user(make_client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    first_user = make_client(sub="user-a", email="a@example.com")
    second_user = make_client(sub="user-b", email="b@example.com")

    first = first_user.post("/career-profile/suggestions/save", json=SUGGESTION).json()
    second = second_user.post("/career-profile/suggestions/save", json=SUGGESTION).json()

    assert first["id_jobPosting"] == second["id_jobPosting"]
    assert len(first_user.get("/user-jobpostings/").json()) == 1
    assert len(second_user.get("/user-jobpostings/").json()) == 1
    assert first_user.get("/companies/outreach/contacts").json()[0]["id_jobPosting"] == first["id_jobPosting"]
    assert second_user.get("/companies/outreach/contacts").json()[0]["id_jobPosting"] == first["id_jobPosting"]


def test_find_email_saves_pasted_email(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()

    response = client.post(
        f"/companies/{saved['id_company']}/find-email",
        json={"website_url": "info@acme.com"},
    )

    assert response.status_code in {200, 202}
    assert response.json()["email"] == "info@acme.com"
    contact = client.get("/companies/outreach/contacts").json()[0]
    assert contact["email"] == "info@acme.com"
    assert contact["outreach_status"] == "to_contact"
    assert contact["contact_type"] == "general"


def test_find_email_rejects_sales_address(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json=SUGGESTION).json()

    response = client.post(
        f"/companies/{saved['id_company']}/find-email",
        json={"website_url": "sales@acme.com"},
    )

    assert response.status_code == 400
    assert client.get("/companies/outreach/contacts").json()[0]["email"] is None


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
    saved = client.post(
        "/career-profile/suggestions/save",
        json={**SUGGESTION, "url": "https://www.itjobs.pt/oferta/1"},
    ).json()

    session_factory = client.app.dependency_overrides
    db_generator = next(iter(session_factory.values()))()
    db = next(db_generator)
    monkeypatch.setattr(ContactEnrichment, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    monkeypatch.setattr(email_finder, "fetch_page", lambda url: None)
    monkeypatch.setattr(ContactEnrichment, "guess_website", lambda name, location=None: "https://acme.com")
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


def test_enrich_finds_site_from_job_url_when_name_does_not_guess(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        **SUGGESTION,
        "company": "Nimbus",
        "url": "https://nimbus.dev/jobs/backend",
    }).json()

    session_factory = client.app.dependency_overrides
    db_generator = next(iter(session_factory.values()))()
    db = next(db_generator)
    monkeypatch.setattr(ContactEnrichment, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: None)
    monkeypatch.setattr(ContactEnrichment, "guess_website", lambda name, location=None: None)
    monkeypatch.setattr(
        ContactEnrichment,
        "find_company_email",
        lambda website: ("jobs@nimbus.dev", "careers", f"{website}/careers"),
    )
    ContactEnrichment.enrich_company(saved["id_company"])

    contact = client.get("/companies/outreach/contacts").json()[0]
    assert contact["email"] == "jobs@nimbus.dev"
    assert contact["website_url"] == "https://nimbus.dev"


def test_enrich_uses_job_ad_email_instead_of_guessed_mailbox(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        **SUGGESTION,
        "company": "Fyld",
        "url": "https://fyld.pt/job-apply/net-developer",
    }).json()

    session_factory = client.app.dependency_overrides
    db_generator = next(iter(session_factory.values()))()
    db = next(db_generator)
    monkeypatch.setattr(ContactEnrichment, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(
        email_finder,
        "fetch_page",
        lambda url: "Send your CV to join@fyld.pt or the DPO at dpo@fyld.pt" if "fyld.pt" in url else None,
    )
    monkeypatch.setattr(ContactEnrichment, "guess_website", lambda name, location=None: "https://fyld.com")
    monkeypatch.setattr(
        ContactEnrichment,
        "find_company_email",
        lambda website: ("fyld@fyld.com", "general", "https://fyld.com/"),
    )
    ContactEnrichment.enrich_company(saved["id_company"])

    contact = client.get("/companies/outreach/contacts").json()[0]
    assert contact["email"] == "join@fyld.pt"
    assert contact["contact_type"] == "careers"
    assert contact["website_url"] == "https://fyld.pt"


def test_enrich_uses_company_site_when_job_board_listing_has_no_email(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        **SUGGESTION,
        "company": "We are META",
        "url": "https://www.net-empregos.com/16100000/net-developer/",
    }).json()

    session_factory = client.app.dependency_overrides
    db_generator = next(iter(session_factory.values()))()
    db = next(db_generator)
    monkeypatch.setattr(ContactEnrichment, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: "Net-Empregos oferta sem contacto")
    monkeypatch.setattr(ContactEnrichment, "guess_website", lambda name, location=None: "https://wearemeta.io")
    monkeypatch.setattr(
        ContactEnrichment,
        "find_company_email",
        lambda website: ("sayhello@wearemeta.io", "general", f"{website}/about")
        if "wearemeta.io" in website
        else ("info@net-empregos.com", "general", website),
    )
    ContactEnrichment.enrich_company(saved["id_company"], "https://www.net-empregos.com", True)

    contact = client.get("/companies/outreach/contacts").json()[0]
    assert contact["email"] == "sayhello@wearemeta.io"
    assert contact["website_url"] == "https://wearemeta.io"


def test_fill_suggestion_emails_uses_job_page_then_company_site(monkeypatch):
    from app.scrappers import email_finder
    from app.services.ContactEnrichment import fill_suggestion_emails

    pages = {"https://jobs.example/vaga": "info@acme.com"}
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: pages.get(url))
    monkeypatch.setattr(email_finder, "guess_website", lambda name, location=None: "https://beta.pt")
    monkeypatch.setattr(
        email_finder,
        "find_company_email",
        lambda website, use_browser=True: ("contacto@beta.pt", "careers", "https://beta.pt/contactos")
        if website == "https://beta.pt"
        else None,
    )

    suggestions = [
        {"company": "Acme", "url": "https://jobs.example/vaga", "email": None},
        {"company": "Beta", "url": "https://jobs.example/sem-email", "email": None},
    ]
    fill_suggestion_emails(suggestions)

    assert suggestions[0]["email"] == "info@acme.com"
    assert suggestions[1]["email"] == "contacto@beta.pt"


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
