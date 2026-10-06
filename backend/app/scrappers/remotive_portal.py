from app.scrappers.common import TAG_QUERIES, build_job, get_json


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
    params = {"limit": limit}
    if tag in CATEGORIES:
        params["category"] = CATEGORIES[tag]
    else:
        params["search"] = TAG_QUERIES.get(tag, tag)
    payload = get_json(API_URL, params)
    jobs = (
        build_job(
            company=job.get("company_name"),
            title=job.get("title"),
            location=job.get("candidate_required_location") or "Worldwide",
            url=job.get("url"),
            industry=[job.get("category") or "", *(job.get("tags") or [])],
            excerpt=job.get("description"),
            source=SOURCE_NAME,
        )
        for job in payload.get("jobs", [])
    )
    return [job for job in jobs if job]
