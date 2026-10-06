def test_partial_contact_update_preserves_omitted_fields(client):
    create_response = client.post(
        "/contacts",
        json={
            "cellphone": "910000000",
            "telephone": "210000000",
            "email": "test@example.com",
        },
    )

    assert create_response.status_code == 200
    contact_id = create_response.json()["id_contact"]

    update_response = client.put(
        f"/contacts/{contact_id}",
        json={"cellphone": "920000000"},
    )

    assert update_response.status_code == 200
    updated_contact = update_response.json()
    assert updated_contact["cellphone"] == "920000000"
    assert updated_contact["telephone"] == "210000000"
    assert updated_contact["email"] == "test@example.com"


def test_company_contact_list_includes_outreach_details(client):
    company_response = client.post(
        "/companies",
        json={"name_company": "Empresa de teste"},
    )
    contact_response = client.post(
        "/contacts",
        json={
            "name_contact": "Equipa de recrutamento",
            "role_contact": "Talent Acquisition",
            "contact_type": "careers",
            "email": "careers@example.com",
            "source_url": "https://example.com/careers",
        },
    )
    company_id = company_response.json()["id_company"]
    contact_id = contact_response.json()["id_contact"]

    link_response = client.post(
        f"/companies/{company_id}/contacts/{contact_id}"
    )
    contacts_response = client.get(f"/companies/{company_id}/contacts")

    assert link_response.status_code == 201
    assert contacts_response.status_code == 200
    assert contacts_response.json() == [
        {
            "id_contact": contact_id,
            "name_contact": "Equipa de recrutamento",
            "role_contact": "Talent Acquisition",
            "contact_type": "careers",
            "cellphone": None,
            "telephone": None,
            "email": "careers@example.com",
            "source_url": "https://example.com/careers",
        }
    ]

    outreach_response = client.get("/companies/outreach/contacts")

    assert outreach_response.status_code == 200
    assert outreach_response.json() == [
        {
            "id_company": company_id,
            "name_company": "Empresa de teste",
            "website_url": None,
            "job_title": None,
            "outreach_status": "to_contact",
            **contacts_response.json()[0],
        }
    ]

    status_response = client.patch(
        f"/companies/{company_id}/contacts/{contact_id}/status",
        json={"outreach_status": "sent"},
    )

    assert status_response.status_code == 200
    assert status_response.json()["outreach_status"] == "sent"