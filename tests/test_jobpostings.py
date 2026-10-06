def test_create_jobposting_with_url(client):
    location_response = client.post(
        "/locations",
        json={
            "street_name": "Rua de teste",
            "zip_code": "1000-001",
            "city": "Lisboa",
        },
    )

    location_id = location_response.json()["id_location"]

    source_response = client.post(
        "/sources",
        json={
            "name_source": "Portal de teste",
            "id_location": location_id,
        },
    )

    source_id = source_response.json()["id_source"]

    response = client.post(
        "/jobpostings",
        json={
            "position_jobPosting": "Engenheiro de software",
            "id_source": source_id,
            "url_jobPosting": "https://example.com/jobs/123",
        },
    )

    assert response.status_code == 200
    assert response.json()["url_jobPosting"] == "https://example.com/jobs/123"

def test_duplicate_jobposting_url_does_not_create_another_jobposting(client):
    location_response = client.post(
        "/locations",
        json={
            "street_name": "Rua de teste",
            "zip_code": "1000-001",
            "city": "Lisboa",
        },
    )
    location_id = location_response.json()["id_location"]

    source_response = client.post(
        "/sources",
        json={
            "name_source": "Portal de teste",
            "id_location": location_id,
        },
    )

    source_id = source_response.json()["id_source"]

    payload = {
        "position_jobPosting": "Engenheiro de software",
        "id_source": source_id,
        "url_jobPosting": "https://example.com/jobs/123",
    }

    first_response = client.post("/jobpostings", json=payload)
    assert first_response.status_code == 200

    second_response = client.post("/jobpostings", json=payload)

    assert second_response.status_code == 200
    assert second_response.json()["id_jobPosting"] == first_response.json()["id_jobPosting"]
    
    list_response = client.get("/jobpostings")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1