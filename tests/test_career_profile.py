from io import BytesIO

from docx import Document


def create_cv_docx() -> bytes:
    document = Document()
    document.add_paragraph("Experiência Profissional")
    document.add_paragraph("Engenheira de Software com Python e React")
    document.add_paragraph("Formação Académica")
    document.add_paragraph("Licenciatura em Engenharia Informática")
    content = BytesIO()
    document.save(content)
    return content.getvalue()


def test_cv_upload_detects_area_and_searches_with_cv_terms(client, monkeypatch):
    search_calls = []

    def fake_search_all_sources(tag, location=None, limit=10):
        search_calls.append({"tag": tag, "location": location, "limit": limit})
        return fake_jobs(), []

    def fake_jobs():
        return [
            {
                "company": "Critical Manufacturing",
                "title": "Software Engineer",
                "url": "https://jobicy.com/jobs/example",
                "location": "Portugal",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "Example US company",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/us-example",
                "location": "Portugal, USA",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "QuickNode",
                "title": "Software Engineer",
                "url": "https://jobicy.com/jobs/quicknode-portugal",
                "location": "Portugal",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "QuickNode",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/quicknode-portugal-usa",
                "location": "Portugal, USA",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "Europe company",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/europe-example",
                "location": "Europe",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "Global company",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/global-example",
                "location": "Remote, Worldwide",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "US remote company",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/remote-us-example",
                "location": "Remote, USA",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
            {
                "company": "US-only company",
                "title": "Senior Software Engineer",
                "url": "https://jobicy.com/jobs/us-only-example",
                "location": "United States",
                "industry": ["Software Engineering"],
                "excerpt": "Python and React experience",
                "source": "Jobicy",
            },
        ]

    monkeypatch.setattr("app.services.CareerProfile.search_all_sources", fake_search_all_sources)

    response = client.post(
        "/career-profile/analyze",
        data={"location": "Portugal"},
        files={
            "file": (
                "cv.docx",
                create_cv_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["cv_saved"] is True
    assert result["areas"][0]["name"] == "Engenharia de Software"
    assert {evidence["section"] for evidence in result["areas"][0]["evidence"]} == {
        "experiencia",
        "formacao",
    }
    assert "python" in result["areas"][0]["search_query"].casefold()
    assert search_calls[0]["tag"] == "software"
    assert search_calls[0]["location"] == "Portugal"
    assert [suggestion["company"] for suggestion in result["suggestions"]] == [
        "Critical Manufacturing",
        "QuickNode",
        "Example US company",
        "Global company",
    ]
    assert [suggestion["location_priority"] for suggestion in result["suggestions"]] == [
        0,
        0,
        1,
        3,
    ]
    assert result["suggestions"][2]["location"] == "Portugal, USA"
    assert "US remote company" not in [suggestion["company"] for suggestion in result["suggestions"]]
    assert "US-only company" not in [suggestion["company"] for suggestion in result["suggestions"]]
    assert result["excluded_location_count"] == 3
    assert result["suggestions"][1]["url"] == "https://jobicy.com/jobs/quicknode-portugal"
    assert result["suggestions"][0]["email"] is None
    assert len(result["location_priority_order"]) == 5
    assert result["suggestions"][0]["source"] == "Jobicy"


def test_cv_upload_rejects_unsupported_file_type(client):
    response = client.post(
        "/career-profile/analyze",
        files={"file": ("cv.txt", b"Engenheiro de Software", "text/plain")},
    )

    assert response.status_code == 400
    assert "PDF ou DOCX" in response.json()["detail"]
def test_cv_suggestions_drop_other_stacks_and_jobs_without_cv_skills(client, monkeypatch):
    def fake_search_all_sources(tag, location=None, limit=10):
        return [
            {"company": "Match", "title": "Backend Software Engineer", "url": "https://x/1", "location": "Portugal",
             "industry": [], "excerpt": "We use Python daily", "source": "Jobicy"},
            {"company": "DotNet", "title": "Senior .NET Software Engineer", "url": "https://x/2", "location": "Portugal",
             "industry": [], "excerpt": "C# and Python", "source": "Jobicy"},
            {"company": "NoSkills", "title": "Software Engineer", "url": "https://x/3", "location": "Portugal",
             "industry": [], "excerpt": "Cobol mainframes", "source": "Jobicy"},
        ], []

    monkeypatch.setattr("app.services.CareerProfile.search_all_sources", fake_search_all_sources)
    response = client.post(
        "/career-profile/analyze",
        data={"location": "Portugal"},
        files={"file": ("cv.docx", create_cv_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    companies = [suggestion["company"] for suggestion in response.json()["suggestions"]]
    assert companies == ["Match"]
    assert "python" in response.json()["suggestions"][0]["matched_skills"]

def test_draft_runs_graph_and_skips_low_fit(client, monkeypatch):
    answers = iter([
        {"fit_score": 80, "fit_reason": "Boa correspondência."},
        {"subject": "Application", "body": "Hello, CV attached."},
        {"fit_score": 10, "fit_reason": "Pouca relação."},
    ])
    monkeypatch.setattr("app.ai.outreach_graph.chat_json", lambda *args, **kwargs: next(answers))
    payload = {"company": "Acme", "title": "Backend Engineer", "cv_skills": ["python"], "matched_skills": ["python"]}

    good = client.post("/career-profile/suggestions/draft", json=payload).json()
    assert good["skipped"] is False
    assert good["subject"] == "Application" and good["fit_score"] == 80

    weak = client.post("/career-profile/suggestions/draft", json=payload).json()
    assert weak["skipped"] is True and weak["body"] is None


def test_draft_force_ignores_low_fit(client, monkeypatch):
    answers = iter([
        {"fit_score": 10, "fit_reason": "Pouca relação."},
        {"subject": "Candidatura", "body": "Olá."},
    ])
    monkeypatch.setattr("app.ai.outreach_graph.chat_json", lambda *args, **kwargs: next(answers))
    result = client.post(
        "/career-profile/suggestions/draft",
        json={"company": "Acme", "title": "Engineer", "cv_skills": ["python"], "force": True},
    ).json()
    assert result["skipped"] is False and result["subject"] == "Candidatura"


def test_draft_returns_503_when_model_unavailable(client, monkeypatch):
    from app.ai.llm import LLMError

    def fail(*args, **kwargs):
        raise LLMError("Ollama offline")

    monkeypatch.setattr("app.ai.outreach_graph.chat_json", fail)
    response = client.post("/career-profile/suggestions/draft", json={"company": "A", "title": "B"})
    assert response.status_code == 503


def test_extract_candidate_name():
    from app.services.CareerProfile import extract_candidate_name

    assert extract_candidate_name("Miguel Santos\nSoftware Engineer") == "Miguel Santos"
    assert extract_candidate_name("\n  Ana Maria Costa  \nPorto") == "Ana Maria Costa"
    assert extract_candidate_name("Curriculum Vitae\nMiguel Santos") == "Curriculum Vitae"
    assert extract_candidate_name("miguel@mail.com\nMiguel") is None
    assert extract_candidate_name("Experiência Profissional 2020-2024") is None


def test_draft_signs_with_candidate_name(client, monkeypatch):
    answers = iter([
        {"fit_score": 90, "fit_reason": "ok"},
        {"subject": "Candidatura", "body": "Olá,\nCV em anexo.\n[Nome]"},
    ])
    monkeypatch.setattr("app.ai.outreach_graph.chat_json", lambda *args, **kwargs: next(answers))
    result = client.post(
        "/career-profile/suggestions/draft",
        json={"company": "Acme", "title": "Dev", "language": "pt", "candidate_name": "Miguel Santos"},
    ).json()
    assert result["body"].endswith("Miguel Santos")
