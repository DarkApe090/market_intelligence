from app.scrappers.common import build_job, get_cached_json, is_european_market, matches_tag, take_fresh


API_URL = "https://remoteok.com/api"
SOURCE_NAME = "Remote OK"


def _repair(text: str | None) -> str:
    """A API manda texto UTF-8 já descodificado como Latin-1 (ex.: "ð\\x9f\\x9a\\x80")."""
    try:
        return (text or "").encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text or ""


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    payload = get_cached_json(API_URL)
    results = []
    for job in payload[1:]:
        tags = job.get("tags") or []
        title = _repair(job.get("position"))
        job_location = _repair(job.get("location")) or "Remote"
        if not matches_tag(tag, f"{title} {' '.join(tags)}"):
            continue
        if not is_european_market(job_location, " ".join(tags), requested=location):
            continue
        built = build_job(
            company=_repair(job.get("company")),
            title=title,
            location=job_location,
            url=job.get("url") or job.get("apply_url"),
            industry=tags,
            excerpt=_repair(job.get("description")),
            source=SOURCE_NAME,
            posted_at=job.get("epoch") or job.get("date"),
        )
        if built:
            results.append(built)
    return take_fresh(results, limit)
