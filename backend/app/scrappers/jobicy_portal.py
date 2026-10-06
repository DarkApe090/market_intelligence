import httpx


API_URL = "https://jobicy.com/api/v2/remote-jobs"
SOURCE_NAME = "Jobicy"


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    response = httpx.get(
        API_URL,
        params={
            "tag": tag,
            "geo": location,
            "count": min(max(limit, 1), 20),
        },
        headers={"User-Agent": "PontoCareerSearch/1.0"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    return [
        {
            "company": job.get("companyName", "").strip(),
            "title": job.get("jobTitle", "").strip(),
            "location": job.get("jobGeo", "").strip(),
            "url": job.get("url", "").strip(),
            "industry": job.get("jobIndustry", []),
            "excerpt": job.get("jobExcerpt", ""),
            "source": SOURCE_NAME,
        }
        for job in payload.get("jobs", [])
        if job.get("companyName") and job.get("jobTitle") and job.get("url")
    ]