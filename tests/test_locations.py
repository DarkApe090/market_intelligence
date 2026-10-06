def test_create_location_without_optional_fields(client):
    response = client.post(
        "/locations",
        json={
            "street_name": "Rua de teste",
            "zip_code": "1000-001",
            "city": "Lisboa",
        },
    )

    assert response.status_code == 200
    location = response.json()
    assert location["district"] is None
    assert location["parish"] is None
    assert location["county"] is None

def test_create_location_without_city_returns_422(client):
    response = client.post(
        "/locations",
        json={
            "street_name": "Rua de teste",
            "zip_code": "1000-001",
        },
    )

    assert response.status_code == 422