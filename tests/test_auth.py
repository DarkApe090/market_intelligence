import base64
import email

import pytest

from app.core.config import settings
from app.services import Auth, GoogleMail
from test_career_profile import create_cv_docx


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def google_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "google_client_id", "id")
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    monkeypatch.setattr(settings, "token_encryption_key", "")
    monkeypatch.setattr(Auth, "KEY_FILE", tmp_path / "secret.key")
    GoogleMail._access_tokens.clear()


def _state_from(client, path):
    url = client.get(path).json()["url"]
    return url.split("state=")[1].split("&")[0]


def _fake_google(monkeypatch, sub="sub-1", email_address="eu@example.com", refresh=True):
    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            return FakeResponse(200)
        payload = {"access_token": "at", "expires_in": 3600}
        if kwargs["data"].get("grant_type") == "authorization_code" and refresh:
            payload["refresh_token"] = "rt-secret"
        return FakeResponse(200, payload)

    monkeypatch.setattr(Auth.httpx, "post", fake_post)
    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    monkeypatch.setattr(
        Auth.httpx, "get",
        lambda *a, **k: FakeResponse(200, {"sub": sub, "email": email_address, "email_verified": True, "name": "Miguel Silva"}),
    )


def test_protected_routes_require_login(make_client):
    anonymous = make_client(login=False)
    for method, path in [
        ("get", "/auth/me"), ("get", "/companies/outreach/contacts"), ("get", "/google/status"),
        ("get", "/locations/"), ("post", "/google/send"), ("delete", "/career-profile/cv"),
    ]:
        assert getattr(anonymous, method)(path).status_code == 401, path


def test_login_flow_creates_user_and_session(make_client, monkeypatch):
    _fake_google(monkeypatch)
    anonymous = make_client(login=False)
    state = _state_from(anonymous, "/auth/login-url")

    bad = anonymous.get("/google/callback?code=x&state=nope", follow_redirects=False)
    assert bad.headers["location"].endswith("?auth=error")
    assert anonymous.get("/auth/me").status_code == 401

    anonymous.cookies.set(Auth.STATE_COOKIE, f"login.{state}")
    ok = anonymous.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert ok.headers["location"].endswith("/")
    assert "httponly" in ok.headers["set-cookie"].lower()

    me = anonymous.get("/auth/me").json()
    assert me["user"]["email"] == "eu@example.com"
    assert me["cv"] is None

    assert anonymous.post("/auth/logout").status_code == 200
    assert anonymous.get("/auth/me").status_code == 401


def test_cross_site_post_is_rejected(client):
    assert client.post("/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/auth/logout", headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_first_user_claims_existing_rows_and_others_are_isolated(make_client, db_session_factory):
    from app.models.Company import Company

    with db_session_factory() as db:
        db.add(Company(name_company="Antiga"))
        db.commit()

    first = make_client("sub-1", "um@example.com")
    second = make_client("sub-2", "dois@example.com")

    assert [c["name_company"] for c in first.get("/companies/").json()] == ["Antiga"]
    assert second.get("/companies/").json() == []

    company_id = first.get("/companies/").json()[0]["id_company"]
    assert second.get(f"/companies/{company_id}").status_code == 404
    assert second.delete(f"/companies/{company_id}/outreach").status_code == 404
    assert second.post(f"/companies/{company_id}/locations/1").status_code == 404


def test_outreach_lists_are_per_user(make_client):
    suggestion = {"company": "Acme", "title": "Dev", "location": "Lisboa", "url": "https://acme.test/job", "source": "Teste"}
    first = make_client("sub-1", "um@example.com")
    second = make_client("sub-2", "dois@example.com")

    assert first.post("/career-profile/suggestions/save", json=suggestion).status_code == 200
    assert second.post("/career-profile/suggestions/save", json=suggestion).json()["company_created"] is True
    assert len(first.get("/companies/outreach/contacts").json()) == 1
    assert len(second.get("/companies/outreach/contacts").json()) == 1


def test_gmail_connect_encrypts_token_and_requires_same_account(client, make_client, monkeypatch, db_session_factory):
    from app.models.User import GoogleAccount

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, f"gmail.{state}")
    ok = client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert ok.headers["location"].endswith("?google=connected")
    assert client.get("/google/status").json()["connected"] is True

    with db_session_factory() as db:
        stored = db.query(GoogleAccount).one().refresh_token_encrypted
    assert "rt-secret" not in stored
    assert Auth.decrypt(stored) == "rt-secret"

    _fake_google(monkeypatch, sub="outra-conta")
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, f"gmail.{state}")
    wrong = client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert wrong.headers["location"].endswith("?google=error")

    other = make_client("sub-2", "dois@example.com")
    assert other.get("/google/status").json()["connected"] is False
    assert client.post("/google/disconnect").json()["connected"] is False


def test_send_attaches_stored_cv(client, make_client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, f"gmail.{state}")
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    sent = {}

    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            sent["raw"] = kwargs["json"]["raw"]
            return FakeResponse(200)
        return FakeResponse(200, {"access_token": "new", "expires_in": 3600})

    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    GoogleMail._access_tokens.clear()

    response = client.post("/google/send", json={"to": "jobs@acme.com", "subject": "Olá", "body": "Corpo"})
    assert response.status_code == 200
    message = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]))
    assert [part.get_filename() for part in message.walk() if part.get_filename()] == ["meu.pdf"]


def test_send_requires_connection_and_valid_recipient(client):
    assert client.post("/google/send", json={"to": "jobs@acme.com", "subject": "a", "body": "b"}).status_code == 502
    assert client.post("/google/send", json={"to": "not-an-email", "subject": "a", "body": "b"}).status_code == 422


def test_stored_cv_is_reanalyzed_without_upload(client, monkeypatch):
    monkeypatch.setattr("app.services.CareerProfile.search_all_sources", lambda *a, **k: ([], []))
    assert client.post("/career-profile/analyze-stored", json={"location": "Portugal"}).status_code == 404

    upload = client.post(
        "/career-profile/analyze",
        data={"location": "Portugal"},
        files={"file": ("cv.docx", create_cv_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload.status_code == 200
    assert client.get("/auth/me").json()["cv"]["filename"] == "cv.docx"

    again = client.post("/career-profile/analyze-stored", json={"location": "Lisboa"})
    assert again.status_code == 200
    assert again.json()["cv_saved"] is True

    assert client.delete("/career-profile/cv").status_code == 200
    assert client.get("/auth/me").json()["cv"] is None
