from app.scrappers.common import TAG_QUERIES, build_job, get_json


API_URL = "https://himalayas.app/jobs/api/search"
SOURCE_NAME = "Himalayas"


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    payload = get_json(API_URL, {"q": TAG_QUERIES.get(tag, tag), "limit": min(max(limit, 1), 20)})
    results = []
    for job in payload.get("jobs", [])[:limit]:
        restrictions = job.get("locationRestrictions") or []
        built = build_job(
            company=job.get("companyName"),
            title=job.get("title"),
            location=", ".join(restrictions) if restrictions else "Worldwide",
            url=job.get("applicationLink") or job.get("guid"),
            industry=[*(job.get("categories") or []), *(job.get("parentCategories") or [])],
            excerpt=job.get("excerpt"),
            source=SOURCE_NAME,
        )
        if built:
            results.append(built)
    return results
