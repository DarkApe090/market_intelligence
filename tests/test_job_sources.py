from datetime import datetime, timedelta, timezone

from app.scrappers import (
    common,
    himalayas_portal,
    itjobs_portal,
    job_sources,
    netempregos_portal,
    remoteok_portal,
    teamlyzer_portal,
    weworkremotely_portal,
)


ITJOBS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title><![CDATA[Software Engineer]]></title>
    <link>https://www.itjobs.pt/oferta/1/software-engineer</link>
    <description><![CDATA[Função: Software Engineer<br />Empresa: Acme PT<br />Tipo: Full-time<br />Contrato: n/d<br />Localidade: Lisboa]]></description>
    <pubDate>Thu, 08 Oct 2026 12:00:00 +0000</pubDate>
  </item>
  <item>
    <title><![CDATA[Backend antigo]]></title>
    <link>https://www.itjobs.pt/oferta/2/backend</link>
    <description><![CDATA[Empresa: Velha<br />Localidade: Porto]]></description>
    <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""

WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Dremio: Software Engineer</title>
    <region>Anywhere in the World</region>
    <category>Full-Stack Programming</category>
    <description>Headquarters: Portugal - Remote</description>
    <pubDate>Thu, 08 Oct 2026 12:00:00 +0000</pubDate>
    <link>https://weworkremotely.com/remote-jobs/dremio-software-engineer</link>
  </item>
  <item>
    <title>Yankee: Software Engineer</title>
    <region>USA</region>
    <category>Programming</category>
    <description>Headquarters: New York, USA</description>
    <pubDate>Thu, 08 Oct 2026 12:00:00 +0000</pubDate>
    <link>https://weworkremotely.com/remote-jobs/yankee-software-engineer</link>
  </item>
</channel></rss>
"""


def test_european_market_keeps_iberia_and_remote():
    assert common.is_european_market("Lisboa")
    assert common.is_european_market("Madrid, España")
    assert common.is_european_market("Europe, EMEA")
    assert common.is_european_market("Anywhere in the World")
    assert not common.is_european_market("USA")
    assert not common.is_european_market("Berlin, Germany")
    assert not common.is_european_market("Remote")
    assert common.is_european_market("Remote", requested="Braga")
    assert not common.is_european_market("Remote, USA", requested="Portugal")
    assert common.is_european_market("Berlin, Germany", requested="Alemanha")
    assert not common.is_european_market("Berlin, Germany", requested="Portugal")


def test_itjobs_passes_city_id_for_braga(monkeypatch):
    seen = []
    itjobs_portal._PLACES = None

    def fake_get(url, params=None, encoding=None):
        if "www.itjobs.pt" in url:
            return '<a href="/emprego?location=4" title="Braga">'
        seen.append(params)
        return ITJOBS_RSS.replace("Localidade: Lisboa", "Localidade: Braga")

    monkeypatch.setattr(itjobs_portal, "get_cached_text", fake_get)
    jobs = itjobs_portal.search_jobs("engenharia de software", "Braga", limit=10)
    assert seen[0]["location"] == "4"
    assert "q" not in seen[0]
    assert jobs[0]["location"] == "Braga"
    assert jobs[0]["title"] == "Software Engineer"


def test_itjobs_parses_fresh_portuguese_roles(monkeypatch):
    seen = []
    itjobs_portal._PLACES = None

    def fake_get(url, params=None, encoding=None):
        if "www.itjobs.pt" in url:
            return (
                '<a href="/emprego?location=1" title="Lisboa">'
                '<a href="/emprego?location=4" title="Braga">'
            )
        seen.append(params)
        city = {"1": "Lisboa", "4": "Braga"}.get((params or {}).get("location"), "Lisboa")
        return ITJOBS_RSS.replace("Localidade: Lisboa", f"Localidade: {city}").replace(
            "/oferta/1/", f"/oferta/{(params or {}).get('location') or '0'}/",
        )

    monkeypatch.setattr(itjobs_portal, "get_cached_text", fake_get)
    jobs = itjobs_portal.search_jobs("software", "Portugal", limit=10)
    assert all(not (params or {}).get("location") for params in seen)
    assert all("q" not in (params or {}) for params in seen)
    assert jobs[0]["location"] == "Lisboa"
    assert jobs[0]["source"] == "ITJobs"
    assert jobs[0]["excerpt"] == "Full-time"
    assert jobs[0]["schedule"] == "full_time"
    assert jobs[0]["work_mode"] == "onsite"
    assert "contract" not in jobs[0]


def test_work_mode_reads_title_and_location_only():
    assert common.work_mode("Flutter Developer - Remote From Portugal", "Lisboa") == "remote"
    assert common.work_mode("Designer", "Porto (Híbrido)") == "hybrid"
    assert common.work_mode("Backend Engineer", "Anywhere in the World") == "remote"
    assert common.work_mode("Remote Monitoring Technician (Hybrid)", "Braga") == "hybrid"
    assert common.work_mode("Contabilista", "Leiria") == "onsite"
    assert common.work_mode("Software Engineer", "Europe") == "remote"


def test_normalize_schedule_from_tipo_and_title():
    assert common.normalize_schedule("Full-time") == "full_time"
    assert common.normalize_schedule("full_time") == "full_time"
    assert common.normalize_schedule("tempo inteiro") == "full_time"
    assert common.normalize_schedule("Part-time") == "part_time"
    assert common.normalize_schedule("", "Designer (tempo parcial)") == "part_time"
    job = common.build_job(
        company="Acme",
        title="Designer part-time",
        location="Lisboa",
        url="https://www.itjobs.pt/oferta/9/designer",
        industry=["Full-time", "Design"],
        excerpt="Part-time",
        source="ITJobs",
        schedule="Full-time",
    )
    assert job["schedule"] == "part_time"
    assert job["work_mode"] == "onsite"
    assert job["industry"] == ["Design"]


def test_remoteok_repairs_double_encoded_text(monkeypatch):
    NOW = int(datetime.now(timezone.utc).timestamp())
    monkeypatch.setattr(remoteok_portal, "get_cached_json", lambda *a, **k: [
        {"legal": "notice"},
        {"company": "Midnite", "position": "Software Engineer", "location": "Europe",
         "url": "https://remoteok.com/1", "tags": ["software"],
         "description": "\u00f0\u009f\u009a\u0080 Why Midnite? Caf\u00c3\u00a9", "epoch": NOW},
        {"company": "Café Lda", "position": "Software Engineer", "location": "Europe",
         "url": "https://remoteok.com/2", "tags": ["software"], "description": "Olá", "epoch": NOW},
    ])
    jobs = remoteok_portal.search_jobs("software", "Portugal", limit=10)
    assert jobs[0]["excerpt"] == "🚀 Why Midnite? Café"
    assert jobs[1]["company"] == "Café Lda"


def test_weworkremotely_drops_usa_only(monkeypatch):
    monkeypatch.setattr(weworkremotely_portal, "get_cached_text", lambda *a, **k: WWR_RSS)
    jobs = weworkremotely_portal.search_jobs("software", "Portugal", limit=10)
    assert [job["company"] for job in jobs] == ["Dremio"]


NETEMPREGOS_HTML = """
<div class="job-item media">
  <h2><a class="oferta-link" href=/16106843/psicologo-clinico-lisboa/>Psicólogo Clínico - LISBOA</a></h2>
  <ul>
    <li><i class="flaticon-calendar"></i> 12-10-2026</li>
    <li><i class="flaticon-pin"></i> Lisboa</li>
    <li><i class="fa fa-tags"></i> Saúde / Medicina</li>
    <li style="font-weight:bold"><i class="flaticon-work"></i> Clínica Norte</li>
  </ul>
</div>
<div class="job-item media">
  <h2><a class="oferta-link" href=/16000001/carpinteiro-porto/>Carpinteiro</a></h2>
  <img alt="Madeiras do Norte" src="/logo.png">
  <ul>
    <li><i class="flaticon-calendar"></i> 01-01-2024</li>
    <li><i class="flaticon-pin"></i> Porto</li>
    <li><i class="fa fa-tags"></i> Construção</li>
  </ul>
</div>
<div class="job-item media">
  <h2><a class="oferta-link" href=/16000002/psicologo-remoto/>Psicólogo (REMOTE from Portugal)</a></h2>
  <ul>
    <li><i class="flaticon-calendar"></i> 13-10-2026</li>
    <li><i class="flaticon-pin"></i> ( Todas as Zonas )</li>
    <li><i class="fa fa-tags"></i> Informática ( Programação )</li>
    <li><i class="fa fa-tags"></i> Informática ( Programação )</li>
    <li style="font-weight:bold"><i class="flaticon-work"></i> Mente Sã</li>
  </ul>
</div>
"""


def test_netempregos_city_keeps_braga_and_drops_braganca():
    assert common.in_requested_city("Braga", "Braga")
    assert common.in_requested_city("Portugal", "Braga")
    assert common.in_requested_city("Lisboa", "Braga", "remote")
    assert not common.in_requested_city("Bragança", "Braga")
    assert not common.in_requested_city("Lisboa", "Braga")


TEAMLYZER_HTML = """
<div class="panel jobcard">
  <div class="jobcard__body">
    <span class="role-tag backend">Backend</span>
    <div class="jobcard__title-row">
      <h4 class="jobcard__title">
        <a class="jobcard__title-link" href="/companies/checkmarx-portugal/job/senior-software-engineer-1">Senior software engineer</a>
      </h4>
    </div>
    <div class="jobcard__meta">
      <a class="jobcard__company" href="/companies/checkmarx-portugal">Checkmarx Portugal</a>
      <span class="jobcard__rating"><i class="fa fa-star"></i> 3.8</span>
      <span class="jobcard__reviews">56 Reviews</span>
    </div>
    <div class="jobcard__meta">
      <span class="jobcard__location"><i class="fa fa-map-marker"></i> Braga (Regime: Híbrido)</span>
      <span class="jobcard__seniority"><i class="fa fa-bar-chart"></i> Sénior</span>
      <span class="jobcard__salary">€44k - 52k<span class="jobcard__salary-label">Bruto anual</span></span>
      <span class="jobcard__on-site" title="No site há 3 semanas"></span>
    </div>
  </div>
</div>
<div class="panel jobcard">
  <div class="jobcard__body">
    <span class="role-tag infraestrutura">Infraestrutura</span>
    <h4 class="jobcard__title">
      <a class="jobcard__title-link" href="/companies/five9/job/cloud-governance-engineer-19474">Cloud governance engineer</a>
    </h4>
    <div class="jobcard__meta">
      <a class="jobcard__company" href="/companies/five9">Five9</a>
    </div>
    <div class="jobcard__meta">
      <span class="jobcard__location"><i class="fa fa-map-marker"></i> Porto (Regime: Híbrido)</span>
      <span class="jobcard__on-site" title="No site há 3 semanas"></span>
    </div>
  </div>
</div>
<div class="panel jobcard">
  <div class="jobcard__body">
    <h4 class="jobcard__title">
      <a class="jobcard__title-link" href="/companies/osquay/job/java-developer-2">Java developer</a>
    </h4>
    <div class="jobcard__meta">
      <a class="jobcard__company" href="/companies/osquay">OSQuay</a>
    </div>
    <div class="jobcard__meta">
      <span class="jobcard__location"><i class="fa fa-map-marker"></i> Portugal (Regime: Full remote)</span>
      <span class="jobcard__on-site" title="Nova"></span>
    </div>
  </div>
</div>
<div class="panel jobcard">
  <div class="jobcard__body">
    <h4 class="jobcard__title">
      <a class="jobcard__title-link" href="/companies/old/job/stale-3">Software engineer antigo</a>
    </h4>
    <div class="jobcard__meta">
      <a class="jobcard__company" href="/companies/old">Velha</a>
    </div>
    <div class="jobcard__meta">
      <span class="jobcard__location"><i class="fa fa-map-marker"></i> Braga (Regime: Escritório)</span>
      <span class="jobcard__on-site" title="No site há 8 semanas"></span>
    </div>
  </div>
</div>
"""


def test_teamlyzer_city_keeps_braga_and_remote_drops_porto(monkeypatch):
    seen = []

    def fake_get(url, params=None, encoding=None):
        seen.append({"url": url, "params": params})
        return TEAMLYZER_HTML

    monkeypatch.setattr(teamlyzer_portal, "get_cached_text", fake_get)
    jobs = teamlyzer_portal.search_jobs("engenharia de software", "Braga, Portugal", limit=10)
    assert seen[0]["url"] == teamlyzer_portal.API_URL
    assert seen[0]["params"]["address"] == "braga"
    assert seen[0]["params"]["order"] == "most_recent"
    assert "q" not in seen[0]["params"]
    assert [job["company"] for job in jobs] == ["OSQuay", "Checkmarx Portugal"]
    assert jobs[0]["work_mode"] == "remote"
    assert jobs[1]["location"] == "Braga"
    assert jobs[1]["work_mode"] == "hybrid"
    assert jobs[1]["source"] == "Teamlyzer"
    assert jobs[1]["rating"] == 3.8
    assert jobs[1]["review_count"] == 56
    assert jobs[1]["salary"] == "€44k - 52k"
    assert jobs[1]["seniority"] == "Sénior"
    assert jobs[1]["company_url"] == "https://pt.teamlyzer.com/companies/checkmarx-portugal"


def test_lookup_company_uses_autocomplete(monkeypatch):
    seen = []
    monkeypatch.setattr(
        teamlyzer_portal,
        "get_cached_json",
        lambda url, params=None, headers=None: seen.append(url) or {
            "results": [
                {
                    "name": "Growintel",
                    "slug": "growintel",
                    "rating": 0,
                    "reviews_job": 0,
                    "reviews_interview": 0,
                },
                {
                    "name": "Growin",
                    "slug": "growin",
                    "rating": 2.9,
                    "reviews_job": 19,
                    "reviews_interview": 111,
                },
            ]
        },
    )
    intel = teamlyzer_portal.lookup_company("Growin – Know to grow")
    assert seen == ["https://pt.teamlyzer.com/users/autocomplete_company/v2/Growin"]
    assert intel == {
        "rating": 2.9,
        "review_count": 130,
        "company_url": "https://pt.teamlyzer.com/companies/growin",
    }


def test_lookup_company_skips_unknown_and_unrated(monkeypatch):
    monkeypatch.setattr(
        teamlyzer_portal,
        "get_cached_json",
        lambda url, params=None, headers=None: {
            "results": [
                {"name": "Outra", "slug": "outra", "rating": 4.1, "reviews_job": 3},
                {"name": "Sem notas", "slug": "sem-notas", "rating": 0, "reviews_job": 0},
            ]
        },
    )
    assert teamlyzer_portal.lookup_company("Empresa Desconhecida Lda") is None
    assert teamlyzer_portal.lookup_company("Sem notas") is None


def test_teamlyzer_portugal_uses_national_listing(monkeypatch):
    seen = []
    monkeypatch.setattr(
        teamlyzer_portal,
        "get_cached_text",
        lambda url, params=None, encoding=None: seen.append(params) or TEAMLYZER_HTML,
    )
    jobs = teamlyzer_portal.search_jobs("engenharia de software", "Portugal", limit=10)
    assert all("address" not in params for params in seen)
    assert all("q" not in params for params in seen)
    assert {job["company"] for job in jobs} >= {"OSQuay", "Checkmarx Portugal"}


def test_netempregos_parses_any_trade_and_drops_stale(monkeypatch):
    seen = []

    def fake_get(url, params=None, encoding=None):
        seen.append({"url": url, "params": params, "encoding": encoding})
        return NETEMPREGOS_HTML

    monkeypatch.setattr(netempregos_portal, "get_cached_text", fake_get)
    jobs = netempregos_portal.search_jobs("psicologo clinico", "Portugal", limit=10)
    assert seen[0]["url"] == netempregos_portal.API_URL
    assert seen[0]["params"]["chaves"] == "psicologo clinico"
    assert seen[0]["encoding"] == "latin-1"
    assert "cidade" not in seen[0]["params"]
    assert [job["company"] for job in jobs] == ["Mente Sã", "Clínica Norte"]
    assert jobs[0]["location"] == "Portugal"
    assert jobs[0]["work_mode"] == "remote"
    assert jobs[0]["excerpt"] == "Informática (Programação)"
    assert jobs[0]["excerpt"] == "Informática (Programação)"
    assert jobs[1]["title"] == "Psicólogo Clínico - LISBOA"
    assert jobs[1]["location"] == "Lisboa"
    assert jobs[1]["source"] == "Net-Empregos"


def test_netempregos_portugal_uses_national_listing(monkeypatch):
    seen = []
    monkeypatch.setattr(
        netempregos_portal,
        "get_cached_text",
        lambda url, params=None, encoding=None: seen.append(params) or NETEMPREGOS_HTML,
    )
    netempregos_portal.search_jobs("software", "Portugal", limit=10)
    assert all("cidade" not in params for params in seen)
    assert all(params.get("chaves") == "software" for params in seen)


def test_weworkremotely_uses_general_feed_for_unknown_trades(monkeypatch):
    seen = {}

    def fake_get(url, params=None):
        seen["url"] = url
        return WWR_RSS.replace("Dremio: Software Engineer", "Madeiras: Carpinteiro")

    monkeypatch.setattr(weworkremotely_portal, "get_cached_text", fake_get)
    jobs = weworkremotely_portal.search_jobs("carpinteiro", "Portugal", limit=10)
    assert seen["url"] == weworkremotely_portal.GENERAL_FEED
    assert [job["company"] for job in jobs] == ["Madeiras"]


def test_is_fresh_keeps_a_job_from_three_weeks_ago():
    now = datetime.now(timezone.utc)
    assert common.is_fresh(now - timedelta(weeks=3))
    assert not common.is_fresh(now - timedelta(days=22))


def test_take_fresh_orders_recent_first():
    now = datetime.now(timezone.utc)
    older = {"title": "old", "posted_at": now - timedelta(days=3)}
    newer = {"title": "new", "posted_at": now - timedelta(hours=2)}
    stale = {"title": "stale", "posted_at": now - timedelta(days=40)}
    assert [job["title"] for job in common.take_fresh([older, stale, newer], 5)] == ["new", "old"]


def test_active_sources_are_portugal_and_european_remote():
    assert [source.SOURCE_NAME for source in job_sources.JOB_SOURCES] == [
        "Net-Empregos",
        "ITJobs",
        "Teamlyzer",
        "We Work Remotely",
        "Remotive",
        "Remote OK",
        "Jobicy",
        "Himalayas",
        "Arbeitnow",
    ]
    assert [source.SOURCE_NAME for source in job_sources.LOCAL_JOB_SOURCES] == [
        "Net-Empregos",
        "ITJobs",
        "Teamlyzer",
    ]


def test_iter_source_results_skips_remote_boards_when_asked(monkeypatch):
    called = []

    class Local:
        SOURCE_NAME = "Local"

        @staticmethod
        def search_jobs(tag, location, limit):
            called.append("Local")
            return [{"company": "A"}]

    class Remote:
        SOURCE_NAME = "Remote"

        @staticmethod
        def search_jobs(tag, location, limit):
            called.append("Remote")
            return [{"company": "B"}]

    monkeypatch.setattr(job_sources, "LOCAL_JOB_SOURCES", (Local,))
    monkeypatch.setattr(job_sources, "JOB_SOURCES", (Local, Remote))
    names = [name for name, _jobs in job_sources.iter_source_results("x", "Braga", 5, include_remote=False)]
    assert names == ["Local"]
    assert called == ["Local"]


def test_himalayas_keeps_europe_and_drops_usa(monkeypatch):
    monkeypatch.setattr(himalayas_portal, "get_cached_json", lambda *a, **k: {
        "jobs": [
            {"companyName": "Lisboa Co", "title": "Engineer", "locationRestrictions": ["Portugal"],
             "applicationLink": "https://himalayas.app/1", "categories": ["Software"]},
            {"companyName": "Yankee", "title": "Engineer", "locationRestrictions": ["USA"],
             "applicationLink": "https://himalayas.app/2", "categories": ["Software"]},
        ],
    })
    jobs = himalayas_portal.search_jobs("software", "Portugal", limit=10)
    assert [job["company"] for job in jobs] == ["Lisboa Co"]


def test_search_all_sources_tolerates_a_failing_source(monkeypatch):
    class Good:
        SOURCE_NAME = "Good"

        @staticmethod
        def search_jobs(tag, location, limit):
            return [{"company": "A", "title": "T", "url": "u"}]

    class Bad:
        SOURCE_NAME = "Bad"

        @staticmethod
        def search_jobs(tag, location, limit):
            raise RuntimeError("down")

    monkeypatch.setattr(job_sources, "JOB_SOURCES", (Good, Bad))
    jobs, failed = job_sources.search_all_sources("software", "Portugal", 5)
    assert len(jobs) == 1
    assert failed == ["Bad"]
