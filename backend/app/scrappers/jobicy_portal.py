from app.scrappers.common import build_job, get_cached_json, is_european_market, take_fresh


API_URL = "https://jobicy.com/api/v2/remote-jobs"
SOURCE_NAME = "Jobicy"


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    payload = get_cached_json(
        API_URL,
        {
            "tag": tag,
            "geo": "Europe",
            "count": min(max(limit, 1), 20),
        },
    )
    results = []
    for job in payload.get("jobs", []):
        job_location = (job.get("jobGeo") or "").strip()
        if not is_european_market(job_location, requested=location):
            continue
        built = build_job(
            company=job.get("companyName"),
            title=job.get("jobTitle"),
            location=job_location or "Europe",
            url=job.get("url"),
            industry=job.get("jobIndustry") or [],
            excerpt=job.get("jobExcerpt"),
            source=SOURCE_NAME,
            posted_at=job.get("pubDate"),
        )
        if built:
            results.append(built)
    return take_fresh(results, limit)
