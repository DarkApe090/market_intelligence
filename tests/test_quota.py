from datetime import datetime, timedelta, timezone

from app.models.User import UsageEvent, User

DRAFT = {"company": "Acme", "title": "Dev", "force": True}


def _fake_draft(monkeypatch):
    monkeypatch.setattr("app.ai.outreach_graph.chat_json", lambda *args, **kwargs: {
        "fit_score": 90, "fit_reason": "ok", "subject": "Candidatura", "body": "Olá.",
    })


def _add_events(db_session_factory, email, kind, count, age):
    with db_session_factory() as db:
        user = db.query(User).filter(User.email == email).one()
        created_at = datetime.now(timezone.utc) - age
        db.add_all(UsageEvent(id_user=user.id_user, kind=kind, created_at=created_at) for _ in range(count))
        db.commit()


def test_draft_quota_blocks_after_limit_and_is_per_user(make_client, monkeypatch):
    _fake_draft(monkeypatch)
    first = make_client("sub-1", "um@example.com")
    second = make_client("sub-2", "dois@example.com")

    for _ in range(30):
        assert first.post("/career-profile/suggestions/draft", json=DRAFT).status_code == 200
    blocked = first.post("/career-profile/suggestions/draft", json=DRAFT)
    assert blocked.status_code == 429
    assert "30 rascunhos" in blocked.json()["detail"]

    assert second.post("/career-profile/suggestions/draft", json=DRAFT).status_code == 200


def test_send_quota_uses_a_24_hour_window(client, db_session_factory):
    _add_events(db_session_factory, "eu@example.com", "send", 25, timedelta(hours=2))
    payload = {"to": "jobs@acme.com", "subject": "Candidatura", "body": "Olá."}

    blocked = client.post("/google/send", json=payload)
    assert blocked.status_code == 429
    assert "25 envios" in blocked.json()["detail"]


def test_old_events_do_not_count(client, db_session_factory, monkeypatch):
    _fake_draft(monkeypatch)
    _add_events(db_session_factory, "eu@example.com", "draft", 30, timedelta(hours=2))

    assert client.post("/career-profile/suggestions/draft", json=DRAFT).status_code == 200


def test_pasted_email_does_not_use_find_email_quota(client, db_session_factory):
    company = client.post("/companies/", json={"name_company": "Acme"}).json()
    _add_events(db_session_factory, "eu@example.com", "find_email", 30, timedelta(minutes=5))

    pasted = client.post(f"/companies/{company['id_company']}/find-email", json={"website_url": "jobs@acme.com"})
    assert pasted.status_code == 202
    searched = client.post(f"/companies/{company['id_company']}/find-email", json={"website_url": "acme.com"})
    assert searched.status_code == 429
