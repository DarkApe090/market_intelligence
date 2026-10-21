import pytest

from app.models.JobPosting import JobPosting
from app.models.Source import Source


@pytest.fixture
def job(db_session_factory):
    with db_session_factory() as db:
        source = Source(name_source="Portal de teste")
        db.add(source)
        db.flush()
        posting = JobPosting(
            position_jobPosting="Engenheiro de software",
            id_source=source.id_source,
            url_jobPosting="https://example.com/jobs/1",
        )
        db.add(posting)
        db.commit()
        return {"id_jobPosting": posting.id_jobPosting}


def test_create_list_and_get_user_jobposting(client, job):

    created = client.post("/user-jobpostings/", json={"id_jobPosting": job["id_jobPosting"]})
    assert created.status_code == 200
    body = created.json()
    assert body["id_jobPosting"] == job["id_jobPosting"]
    assert body["seen_at"] is None

    again = client.post("/user-jobpostings/", json={"id_jobPosting": job["id_jobPosting"]})
    assert again.status_code == 200
    assert again.json()["id_jobPosting"] == job["id_jobPosting"]

    listed = client.get("/user-jobpostings/").json()
    assert len(listed) == 1
    assert listed[0]["id_jobPosting"] == job["id_jobPosting"]

    fetched = client.get(f"/user-jobpostings/{job['id_jobPosting']}")
    assert fetched.status_code == 200
    assert fetched.json()["id_jobPosting"] == job["id_jobPosting"]


def test_create_user_jobposting_returns_404_for_unknown_job(client):
    response = client.post("/user-jobpostings/", json={"id_jobPosting": 999})
    assert response.status_code == 404
    assert response.json()["detail"] == "Job posting not found"


def test_mark_seen_and_update_seen_at(client, job):
    client.post("/user-jobpostings/", json={"id_jobPosting": job["id_jobPosting"]})

    seen = client.patch(f"/user-jobpostings/{job['id_jobPosting']}/seen")
    assert seen.status_code == 200
    assert seen.json()["seen_at"] is not None

    updated = client.put(
        f"/user-jobpostings/{job['id_jobPosting']}",
        json={"seen_at": None},
    )
    assert updated.status_code == 200
    assert updated.json()["seen_at"] is None


def test_delete_user_jobposting(client, job):
    client.post("/user-jobpostings/", json={"id_jobPosting": job["id_jobPosting"]})

    deleted = client.delete(f"/user-jobpostings/{job['id_jobPosting']}")
    assert deleted.status_code == 200
    assert client.get(f"/user-jobpostings/{job['id_jobPosting']}").status_code == 404
    assert client.get("/user-jobpostings/").json() == []


def test_user_jobposting_is_isolated_per_user(make_client, job):
    owner = make_client(sub="owner", email="owner@example.com")
    other = make_client(sub="other", email="other@example.com")
    owner.post("/user-jobpostings/", json={"id_jobPosting": job["id_jobPosting"]})

    assert other.get("/user-jobpostings/").json() == []
    assert other.get(f"/user-jobpostings/{job['id_jobPosting']}").status_code == 404
    assert other.patch(f"/user-jobpostings/{job['id_jobPosting']}/seen").status_code == 404
    assert other.delete(f"/user-jobpostings/{job['id_jobPosting']}").status_code == 404


def test_anonymous_cannot_access_user_jobpostings(make_client):
    anonymous = make_client(login=False)
    assert anonymous.get("/user-jobpostings/").status_code == 401
    assert anonymous.post("/user-jobpostings/", json={"id_jobPosting": 1}).status_code == 401
