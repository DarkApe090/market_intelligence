import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.services.JobSearch import fold_analysis
from app.database.connection import get_db
from app.main import app
from app.services import Auth


def analysis_from_response(response):
    if "text/event-stream" in response.headers.get("content-type", ""):
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        return fold_analysis(events)
    return response.json()

@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def make_client(db_session_factory):
    """Cria clientes autenticados como utilizadores diferentes sobre a mesma base de dados."""
    clients = []

    def factory(sub: str = "sub-1", email: str = "eu@example.com", login: bool = True):
        test_client = TestClient(app)
        clients.append(test_client)
        if login:
            db = db_session_factory()
            try:
                user = Auth.upsert_user(db, {"sub": sub, "email": email, "name": "Miguel Silva"})
                test_client.cookies.set(Auth.SESSION_COOKIE, Auth.create_session(db, user))
            finally:
                db.close()
        return test_client

    yield factory
    for test_client in clients:
        test_client.close()


@pytest.fixture
def client(make_client):
    return make_client()

@pytest.fixture(autouse=True)
def no_browser_fallback(monkeypatch):
    from app.scrappers import email_finder

    monkeypatch.setattr(email_finder, "USE_BROWSER_FALLBACK", False)
    monkeypatch.setattr(email_finder, "fetch_page", lambda url: None)
    monkeypatch.setattr(email_finder, "guess_website", lambda name, location=None: None)


@pytest.fixture(autouse=True)
def no_teamlyzer_lookup(monkeypatch):
    monkeypatch.setattr("app.services.JobSearch.lookup_company", lambda name: None)

