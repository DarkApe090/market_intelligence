def test_create_and_get_company(client):
    create_response = client.post(
        "/companies",
        json={"name_company": "Empresa de teste"},
    )

    assert create_response.status_code == 200
    company = create_response.json()
    assert company["name_company"] == "Empresa de teste"

    get_response = client.get(f"/companies/{company['id_company']}")

    assert get_response.status_code == 200
    assert get_response.json() == company


def test_get_missing_company_returns_404(client):
    response = client.get("/companies/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


def test_update_and_delete_company(client):
    create_response = client.post(
        "/companies",
        json={"name_company": "Empresa Inicial"}
    )

    company_id = create_response.json()["id_company"]

    update_response = client.put(
        f"/companies/{company_id}",
        json={"name_company": "Empresa atualizada"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["name_company"] == "Empresa atualizada"

    delete_response = client.delete(f"/companies/{company_id}")
    assert delete_response.status_code == 200

    get_response = client.get(f"/companies/{company_id}")
    assert get_response.status_code == 404