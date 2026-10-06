from app.scrappers.common import build_job, get_cached_json, matches_tag


API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE_NAME = "Arbeitnow"


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    payload = get_cached_json(API_URL)
    results = []
    for job in payload.get("data", []):
        tags = job.get("tags") or []
        title = job.get("title") or ""
        if not matches_tag(tag, f"{title} {' '.join(tags)}"):
            continue

        if job.get("remote"):
            job_location = "Remote"
        elif job.get("location"):
            job_location = f"{job['location']}, Germany"
        else:
            job_location = "Germany"

        built = build_job(
            company=job.get("company_name"),
            title=title,
            location=job_location,
            url=job.get("url"),
            industry=tags,
            excerpt=job.get("description"),
            source=SOURCE_NAME,
        )
        if built:
            results.append(built)
        if len(results) >= limit:
            break
    return results
