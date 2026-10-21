import base64
import email
import email.policy

import pytest

from app.core.config import settings
from app.services import Auth, GoogleMail
from conftest import analysis_from_response
from test_career_profile import create_cv_docx


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = {"content-type": "application/json"}
        self.text = ""

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def google_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "google_client_id", "id")
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    monkeypatch.setattr(settings, "token_encryption_key", "")
    monkeypatch.setattr(Auth, "KEY_FILE", tmp_path / "secret.key")
    GoogleMail._access_tokens.clear()
    GoogleMail._mail_read_ok.clear()


def _state_from(client, path="/auth/login-url?accepted=1"):
    from urllib.parse import unquote

    url = client.get(path).json()["url"]
    return unquote(url.split("state=")[1].split("&")[0])


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
    monkeypatch.setattr(GoogleMail.httpx, "get", lambda *a, **k: FakeResponse(200, {"messages": []}))
    monkeypatch.setattr(
        Auth.httpx, "get",
        lambda *a, **k: FakeResponse(200, {"sub": sub, "email": email_address, "email_verified": True, "name": "Miguel Silva"}),
    )


def test_protected_routes_require_login(make_client):
    anonymous = make_client(login=False)
    for method, path in [
        ("get", "/auth/me"), ("get", "/companies/outreach/contacts"), ("get", "/google/status"),
        ("get", "/user-jobpostings/"), ("post", "/google/send"), ("delete", "/career-profile/cv"),
    ]:
        assert getattr(anonymous, method)(path).status_code == 401, path


def test_shared_catalog_is_not_writable(client):
    for method, path in [
        ("post", "/jobpostings/"), ("delete", "/jobpostings/1"), ("put", "/sources/1"),
        ("delete", "/locations/1"), ("post", "/skills/"), ("delete", "/jobpostings/1/skills/1"),
        ("post", "/companies/1/locations/1"), ("post", "/jobpostings/1/contacts/1"),
    ]:
        assert getattr(client, method)(path).status_code in {404, 405}, path


def test_login_flow_creates_user_and_session(make_client, monkeypatch):
    _fake_google(monkeypatch)
    anonymous = make_client(login=False)
    state = _state_from(anonymous)

    bad = anonymous.get("/google/callback?code=x&state=nope", follow_redirects=False)
    assert bad.status_code == 200
    assert "auth=error" in bad.text
    assert anonymous.get("/auth/me").status_code == 401

    anonymous.cookies.set(Auth.STATE_COOKIE, state)
    ok = anonymous.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert ok.status_code == 200
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert Auth.SESSION_COOKIE in ok.headers.get("set-cookie", "")

    me = anonymous.get("/auth/me").json()
    assert me["user"]["email"] == "eu@example.com"
    assert me["cv"] is None

    assert anonymous.post("/auth/logout").status_code == 200
    assert anonymous.get("/auth/me").status_code == 401


def test_login_redirect_sets_state_cookie(make_client):
    anonymous = make_client(login=False)
    response = anonymous.get("/auth/login?accepted=1", follow_redirects=False)
    assert response.status_code in {302, 307}
    location = response.headers["location"]
    assert "accounts.google.com" in location
    assert "login." in location
    assert "code_challenge=" in location
    assert "code_challenge_method=S256" in location
    assert Auth.STATE_COOKIE in response.headers.get("set-cookie", "")


def test_login_callback_works_without_state_cookie(make_client, monkeypatch):
    exchanged = {}

    def fake_post(url, **kwargs):
        if kwargs.get("data", {}).get("grant_type") == "authorization_code":
            exchanged.update(kwargs["data"])
            return FakeResponse(200, {"access_token": "at", "expires_in": 3600})
        return FakeResponse(200)

    monkeypatch.setattr(Auth.httpx, "post", fake_post)
    monkeypatch.setattr(
        Auth.httpx, "get",
        lambda *a, **k: FakeResponse(200, {"sub": "sub-1", "email": "eu@example.com", "email_verified": True, "name": "Miguel Silva"}),
    )
    state = _state_from(make_client(login=False))
    anonymous = make_client(login=False)

    ok = anonymous.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert ok.status_code == 200
    assert anonymous.get("/auth/me").status_code == 200
    assert exchanged.get("code_verifier")
    assert exchanged.get("redirect_uri", "").endswith("/google/callback")


def test_login_callback_rejects_forged_state(make_client, monkeypatch):
    _fake_google(monkeypatch)
    anonymous = make_client(login=False)
    forged = "login.9999999999.nonce.00000000000000000000000000000000"
    bad = anonymous.get(f"/google/callback?code=x&state={forged}", follow_redirects=False)
    assert bad.status_code == 200
    assert "auth=error" in bad.text
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


def test_outreach_lists_are_per_user(make_client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
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
    client.cookies.set(Auth.STATE_COOKIE, state)
    ok = client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert ok.status_code == 200
    assert "google=connected" in ok.text
    status = client.get("/google/status").json()
    assert status["connected"] is True
    assert status["can_follow_replies"] is True

    with db_session_factory() as db:
        stored = db.query(GoogleAccount).one().refresh_token_encrypted
    assert "rt-secret" not in stored
    assert Auth.decrypt(stored) == "rt-secret"

    _fake_google(monkeypatch, sub="outra-conta")
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    wrong = client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    assert wrong.status_code == 200
    assert "google=error" in wrong.text

    other = make_client("sub-2", "dois@example.com")
    assert other.get("/google/status").json()["connected"] is False
    assert client.post("/google/disconnect").json()["connected"] is False


def test_send_attaches_stored_cv(client, make_client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
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


def test_apply_sends_the_reviewed_email_to_company(client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Acme Lda",
        "title": "Software Engineer",
        "url": "https://example.com/job/apply-1",
        "source": "Remote OK",
        "email": "jobs@acme.com",
    }).json()

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    def no_ai(*args, **kwargs):
        raise AssertionError("O envio não pode chamar a IA.")

    monkeypatch.setattr("app.ai.outreach_graph.chat_json", no_ai)

    sent = {}

    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            sent["raw"] = kwargs["json"]["raw"]
            return FakeResponse(200)
        return FakeResponse(200, {"access_token": "new", "expires_in": 3600})

    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    GoogleMail._access_tokens.clear()

    apply_url = f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply"
    assert client.post(apply_url, json={}).status_code == 422
    assert client.post(apply_url, json={"subject": "Candidatura", "body": "   "}).status_code == 422
    assert "raw" not in sent

    response = client.post(apply_url, json={"subject": " Candidatura ", "body": "Olá, sou o Miguel (editado)."})
    assert response.status_code == 200
    assert response.json() == {"to": "jobs@acme.com"}
    message = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]), policy=email.policy.default)
    assert "jobs@acme.com" in str(message["To"])
    assert message["Subject"] == "Candidatura"
    assert "(editado)" in next(part for part in message.walk() if part.get_content_type() == "text/plain").get_content()
    assert [part.get_filename() for part in message.walk() if part.get_filename()] == ["meu.pdf"]
    assert client.get("/companies/outreach/contacts").json()[0]["outreach_status"] == "sent"


def test_gmail_status_flags_missing_readonly(client, monkeypatch):
    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    monkeypatch.setattr(GoogleMail.httpx, "get", lambda *a, **k: FakeResponse(403))
    GoogleMail._access_tokens.clear()
    GoogleMail._mail_read_ok.clear()
    status = client.get("/google/status").json()
    assert status["connected"] is True
    assert status["can_follow_replies"] is False


def test_gmail_auth_url_asks_send_and_readonly(client, monkeypatch):
    _fake_google(monkeypatch)
    url = client.get("/google/auth-url").json()["url"]
    assert "gmail.send" in url
    assert "gmail.readonly" in url


def test_outreach_marks_replied_from_gmail_thread(client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Acme Lda",
        "title": "Software Engineer",
        "url": "https://example.com/job/reply-1",
        "source": "Remote OK",
        "email": "jobs@acme.com",
    }).json()

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            return FakeResponse(200, {"id": "msg-1", "threadId": "thread-1"})
        return FakeResponse(200, {"access_token": "new", "expires_in": 3600})

    def fake_get(url, **kwargs):
        if "threads/thread-1" in str(url):
            return FakeResponse(200, {
                "messages": [
                    {"payload": {"headers": [{"name": "From", "value": "Miguel Silva <eu@example.com>"}]}},
                    {
                        "internalDate": "1710000000000",
                        "payload": {
                            "mimeType": "text/plain",
                            "headers": [
                                {"name": "From", "value": "Acme Jobs <jobs@acme.com>"},
                                {"name": "Subject", "value": "Re: Candidatura"},
                            ],
                            "body": {"data": base64.urlsafe_b64encode(b"Obrigado, falamos na proxima semana.").decode().rstrip("=")},
                        },
                    },
                ],
            })
        return FakeResponse(200, {"messages": []})

    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    monkeypatch.setattr(GoogleMail.httpx, "get", fake_get)
    GoogleMail._access_tokens.clear()

    assert client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Candidatura", "body": "Olá."},
    ).status_code == 200
    assert client.get("/companies/outreach/contacts").json()[0]["outreach_status"] == "replied"
    reply = client.get(f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/reply").json()
    assert reply["sender"] == "Acme Jobs <jobs@acme.com>"
    assert reply["subject"] == "Re: Candidatura"
    assert "proxima semana" in reply["body"]
    assert reply["outreach_status"] == "replied"


def _gmail_data(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode()


def test_gmail_reply_prefers_html_and_strips_css():
    css_plain = (
        "@media (prefers-color-scheme: dark ) { table.body .btn a { background-color: #102C3C !important; "
        "color: #FFFFFF !important; border: solid 1px #102C3C !important; }}"
        "@media all and (max-width: 800px) { table.body p { font-size: 16px !important; } }"
        "Dellent Consulting   Olá Miguel,Agradecemos, desde já, a tua candidatura."
    )
    html_body = """
    <html><head><style>
    @media (prefers-color-scheme: dark ) { table.body .btn a { background-color: #102C3C !important; color: #FFFFFF !important; }}
    table.body p { font-size: 16px !important; }
    </style></head>
    <body>
      <table>
        <tr><td>Dellent Consulting</td></tr>
        <tr><td><p>Olá Miguel,</p><p>Agradecemos, desde já, a tua candidatura e interesse na Dellent!</p></td></tr>
      </table>
    </body></html>
    """
    body = GoogleMail._message_body({
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _gmail_data(css_plain)}},
            {"mimeType": "text/css", "body": {"data": _gmail_data("@media all { a { color: red !important; } }")}},
            {"mimeType": "text/html", "body": {"data": _gmail_data(html_body)}},
        ],
    })
    assert "@media" not in body
    assert "!important" not in body
    assert "table.body" not in body
    assert "Olá Miguel" in body
    assert "Agradecemos" in body
    assert "Olá Miguel,Agradecemos" not in body
    assert "Dellent Consulting" in body


def test_gmail_reply_cleans_css_dumped_as_plain_text():
    dumped = (
        "@media (prefers-color-scheme: dark ) { table.body .btn a { color: #FFFFFF !important; }}"
        "@media all { .ExternalClass { width: 100%; } }"
        "Dellent Consulting   Olá Miguel,Agradecemos a tua candidatura."
    )
    body = GoogleMail._message_body({
        "mimeType": "text/plain",
        "body": {"data": _gmail_data(dumped)},
    })
    assert "@media" not in body
    assert "!important" not in body
    assert "prefers-color-scheme" not in body
    assert "ExternalClass" not in body
    assert "Dellent Consulting" in body
    assert "Olá Miguel" in body
    assert "Agradecemos a tua candidatura" in body
    assert "Olá Miguel,Agradecemos" not in body


def test_gmail_reply_detects_rejection_copy():
    assert GoogleMail.is_rejection(
        "Avaliação da candidatura",
        "Após analisarmos o teu perfil, informamos que, para já, não iremos avançar para a próxima fase.",
    )
    assert GoogleMail.is_rejection("Update", "We will not be moving forward with your application.")
    assert not GoogleMail.is_rejection("Entrevista", "Gostaríamos de avançar para a próxima fase. Podes na quinta?")


def test_outreach_archives_negative_gmail_reply(client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Dellent",
        "title": "Fullstack Developer",
        "url": "https://example.com/job/dellent-1",
        "source": "ITJobs",
        "email": "careers@dellentconsulting.com",
    }).json()

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    body = (
        "Olá Miguel, após analisarmos atentamente o teu perfil, informamos que, "
        "para já, não iremos avançar para a próxima fase do recrutamento."
    )

    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            return FakeResponse(200, {"id": "msg-d", "threadId": "thread-d"})
        return FakeResponse(200, {"access_token": "new", "expires_in": 3600})

    def fake_get(url, **kwargs):
        if "threads/thread-d" in str(url):
            return FakeResponse(200, {
                "messages": [
                    {"payload": {"headers": [{"name": "From", "value": "Miguel Silva <eu@example.com>"}]}},
                    {
                        "internalDate": "1710000000000",
                        "payload": {
                            "mimeType": "text/plain",
                            "headers": [
                                {"name": "From", "value": "Dellent Jobs <careers@dellentconsulting.com>"},
                                {"name": "Subject", "value": "Avaliação da candidatura"},
                            ],
                            "body": {"data": _gmail_data(body)},
                        },
                    },
                ],
            })
        return FakeResponse(200, {"messages": []})

    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    monkeypatch.setattr(GoogleMail.httpx, "get", fake_get)
    GoogleMail._access_tokens.clear()

    assert client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Candidatura", "body": "Olá."},
    ).status_code == 200
    listed = client.get("/companies/outreach/contacts").json()[0]
    assert listed["outreach_status"] == "rejected"
    blocked = client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Candidatura", "body": "Olá de novo."},
    )
    assert blocked.status_code == 400
    reply = client.get(f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/reply").json()
    assert reply["outreach_status"] == "rejected"
    assert "não iremos avançar" in reply["body"]


def test_outreach_marks_replied_from_company_inbox(client, monkeypatch, db_session_factory):
    from app.models.User import User
    from app.services.UserCv import save_cv

    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Beta Lda",
        "title": "Dev",
        "url": "https://example.com/job/reply-2",
        "source": "Remote OK",
        "email": "careers@beta.com",
    }).json()

    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    def fake_post(url, **kwargs):
        if kwargs.get("json") is not None:
            return FakeResponse(200)
        return FakeResponse(200, {"access_token": "new", "expires_in": 3600})

    queries = []

    def fake_get(url, **kwargs):
        query = str((kwargs.get("params") or {}).get("q", ""))
        queries.append(query)
        if "from:@beta.com" in query:
            return FakeResponse(200, {"messages": [{"id": "in-1"}]})
        return FakeResponse(200, {"messages": []})

    monkeypatch.setattr(GoogleMail.httpx, "post", fake_post)
    monkeypatch.setattr(GoogleMail.httpx, "get", fake_get)
    GoogleMail._access_tokens.clear()

    assert client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Olá", "body": "Corpo"},
    ).status_code == 200
    listed = client.get("/companies/outreach/contacts").json()[0]
    assert listed["outreach_status"] == "replied"
    assert listed["sent_at"] is not None
    reply_query = next(query for query in queries if "from:@beta.com" in query)
    assert " after:" in reply_query
    assert "in:inbox" not in reply_query


def test_reply_sync_recovers_thread_of_older_sends(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Delta",
        "title": "Dev",
        "url": "https://example.com/job/reply-4",
        "source": "ITJobs",
        "email": "jobs@delta.pt",
    }).json()
    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)
    client.patch(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/status",
        json={"outreach_status": "sent"},
    )

    def fake_get(url, **kwargs):
        query = str((kwargs.get("params") or {}).get("q", ""))
        if query == "in:sent to:jobs@delta.pt":
            return FakeResponse(200, {"messages": [{"id": "sent-1", "threadId": "thread-old"}]})
        if str(url).endswith("/messages/sent-1"):
            return FakeResponse(200, {"id": "sent-1", "internalDate": "1760000000000"})
        if "threads/thread-old" in str(url):
            return FakeResponse(200, {"messages": [
                {"payload": {"headers": [{"name": "From", "value": "eu@example.com"}]}},
                {"payload": {"headers": [{"name": "From", "value": "Delta <no-reply@ats.example>"}]}},
            ]})
        return FakeResponse(200, {"messages": []})

    monkeypatch.setattr(GoogleMail.httpx, "post", lambda *a, **k: FakeResponse(200, {"access_token": "new", "expires_in": 3600}))
    monkeypatch.setattr(GoogleMail.httpx, "get", fake_get)
    GoogleMail._access_tokens.clear()

    listed = client.get("/companies/outreach/contacts").json()[0]
    assert listed["outreach_status"] == "replied"
    assert listed["sent_at"].startswith("2025-10-09")


def test_gmail_reply_sync_survives_missing_permission(client, monkeypatch, db_session_factory):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Gamma",
        "title": "Dev",
        "url": "https://example.com/job/reply-3",
        "source": "Remote OK",
        "email": "jobs@gamma.com",
    }).json()
    _fake_google(monkeypatch)
    state = _state_from(client, "/google/auth-url")
    client.cookies.set(Auth.STATE_COOKIE, state)
    client.get(f"/google/callback?code=x&state={state}", follow_redirects=False)

    monkeypatch.setattr(GoogleMail.httpx, "post", lambda *a, **k: FakeResponse(
        200, {"id": "msg-1", "threadId": "thread-x"} if k.get("json") else {"access_token": "new", "expires_in": 3600}
    ))
    monkeypatch.setattr(GoogleMail.httpx, "get", lambda *a, **k: FakeResponse(403))
    GoogleMail._access_tokens.clear()

    from app.models.User import User
    from app.services.UserCv import save_cv
    with db_session_factory() as db:
        save_cv(db, db.query(User).one(), "meu.pdf", b"%PDF-1.4 test", "Miguel Silva", ["Python"])

    assert client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Olá", "body": "Corpo"},
    ).status_code == 200
    listed = client.get("/companies/outreach/contacts")
    assert listed.status_code == 200
    assert listed.json()[0]["outreach_status"] == "sent"


def test_apply_requires_contact_email(client, monkeypatch):
    monkeypatch.setattr("app.controllers.CareerProfile.enrich_company", lambda *args, **kwargs: None)
    saved = client.post("/career-profile/suggestions/save", json={
        "company": "Beta",
        "title": "Dev",
        "url": "https://example.com/job/apply-2",
        "source": "Remote OK",
    }).json()
    response = client.post(
        f"/companies/{saved['id_company']}/contacts/{saved['id_contact']}/apply",
        json={"subject": "Candidatura", "body": "Olá."},
    )
    assert response.status_code == 400


def test_stored_cv_is_reanalyzed_without_upload(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.CareerProfile.chat_json",
        lambda *a, **k: {
            "candidate_name": "Miguel Silva",
            "areas": [{
                "name": "Engenharia de Software",
                "search_tag": "software",
                "role_terms": ["software engineer"],
                "matched_skills": ["python"],
                "confidence": "high",
                "evidence": [{"text": "Python", "section": "competencias"}],
            }],
        },
    )
    monkeypatch.setattr("app.services.JobSearch.fetch_source_batches", lambda *a, **k: iter(()))
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
    assert analysis_from_response(again)["areas"]

    assert client.delete("/career-profile/cv").status_code == 200
    assert client.get("/auth/me").json()["cv"] is None


def test_callback_uri_uses_public_redirect(monkeypatch):
    monkeypatch.setattr(settings, "google_redirect_uri", "https://api.example.com/google/callback")

    class Request:
        base_url = "http://127.0.0.1:8000/"

    assert Auth.callback_uri(Request()) == "https://api.example.com/google/callback"


def test_callback_uri_follows_loopback_host(monkeypatch):
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/google/callback")

    class Request:
        base_url = "http://127.0.0.1:8000/"

    assert Auth.callback_uri(Request()) == "http://127.0.0.1:8000/google/callback"


def test_https_urls_force_secure_cookies():
    from app.core.config import Settings

    split = Settings(
        database_url="postgresql://u:p@localhost/db",
        frontend_url="https://app.example.com",
        google_redirect_uri="https://api.example.com/google/callback",
        cookie_secure=False,
        cookie_samesite="lax",
    )
    assert split.cookie_secure is True
    assert split.cookie_samesite == "none"

    same_host = Settings(
        database_url="postgresql://u:p@localhost/db",
        frontend_url="https://ponto.example.com",
        google_redirect_uri="https://ponto.example.com/google/callback",
        cookie_secure=False,
        cookie_samesite="lax",
    )
    assert same_host.cookie_secure is True
    assert same_host.cookie_samesite == "lax"


def test_login_requires_terms_acceptance(make_client):
    anonymous = make_client(login=False)
    denied = anonymous.get("/auth/login", follow_redirects=False)
    assert denied.status_code == 400
    assert "termos" in denied.json()["detail"].casefold()
    assert anonymous.get("/auth/login-url").status_code == 400
    allowed = anonymous.get("/auth/login?accepted=1", follow_redirects=False)
    assert allowed.status_code in {302, 307}


def test_legal_pages_are_public(make_client):
    anonymous = make_client(login=False)
    privacy = anonymous.get("/privacidade")
    terms = anonymous.get("/termos")
    assert privacy.status_code == 200
    assert "privacidade" in privacy.text.casefold()
    assert terms.status_code == 200
    assert "termos" in terms.text.casefold()


def test_export_and_delete_account(client):
    company = client.post("/companies/", json={"name_company": "Acme"}).json()
    exported = client.get("/auth/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["user"]["email"] == "eu@example.com"
    assert body["user"]["terms_accepted_at"]
    assert any(row["name"] == "Acme" for row in body["companies"])
    assert "content" not in (body["cv"] or {})

    deleted = client.delete("/auth/account")
    assert deleted.status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert client.get(f"/companies/{company['id_company']}").status_code == 401
