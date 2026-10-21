from app.scrappers.common import TAG_QUERIES, build_job, get_cached_json, is_european_market, take_fresh


API_URL = "https://remotive.com/api/remote-jobs"
SOURCE_NAME = "Remotive"


CATEGORIES = {
    "software": "software-dev",
    "data": "data",
    "devops": "devops",
    "design": "design",
    "marketing": "marketing",
    "finance": "finance-legal",
}


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    params = {"limit": max(limit * 4, 40)}
    if tag in CATEGORIES:
        params["category"] = CATEGORIES[tag]
    else:
        params["search"] = TAG_QUERIES.get(tag, tag)
    payload = get_cached_json(API_URL, params)
    results = []
    for job in payload.get("jobs", []):
        job_location = job.get("candidate_required_location") or "Worldwide"
        if not is_european_market(job_location, " ".join(job.get("tags") or []), requested=location):
            continue
        built = build_job(
            company=job.get("company_name"),
            title=job.get("title"),
            location=job_location,
            url=job.get("url"),
            industry=[job.get("category") or "", *(job.get("tags") or [])],
            excerpt=job.get("description"),
            source=SOURCE_NAME,
            posted_at=job.get("publication_date"),
        )
        if built:
            results.append(built)
    return take_fresh(results, limit)
