def test_create_source_with_location(client):
    location_response = client.post(
        "/locations",
        json={
            "street_name": "Rua de teste",
            "zip_code": "1000-001",
            "city": "Lisboa",
        },
    )

    assert location_response.status_code == 200
    location_id = location_response.json()["id_location"]

    source_response = client.post(
        "/sources",
        json={
            "name_source": "Site de teste",
            "id_location": location_id,
        },
    )

    assert source_response.status_code == 200
    source = source_response.json()
    assert source["name_source"] == "Site de teste"
    assert source["id_location"] == location_id

def test_create_source_without_location_returns_422(client):
    response = client.post(
        "/sources",
        json={"name_source": "Site sem localizaçao"},
    )

    assert response.status_code == 422