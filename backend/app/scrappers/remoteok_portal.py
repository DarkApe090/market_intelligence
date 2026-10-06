from app.scrappers.common import build_job, get_cached_json, matches_tag


API_URL = "https://remoteok.com/api"
SOURCE_NAME = "Remote OK"


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    payload = get_cached_json(API_URL)
    results = []
    # O primeiro elemento do feed são os termos legais, não uma vaga.
    for job in payload[1:]:
        tags = job.get("tags") or []
        title = job.get("position") or ""
        if not matches_tag(tag, f"{title} {' '.join(tags)}"):
            continue

        built = build_job(
            company=job.get("company"),
            title=title,
            location=job.get("location") or "Remote",
            url=job.get("url") or job.get("apply_url"),
            industry=tags,
            excerpt=job.get("description"),
            source=SOURCE_NAME,
        )
        if built:
            results.append(built)
        if len(results) >= limit:
            break
    return results
