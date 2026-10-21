import html
import re
from datetime import datetime, timezone

from app.scrappers.common import (
    FEED_PAGES,
    build_job,
    countrywide_portugal,
    get_cached_text,
    in_requested_city,
    requested_city,
    strip_html,
    take_fresh,
)


API_URL = "https://www.net-empregos.com/pesquisa-empregos.asp"
SOURCE_NAME = "Net-Empregos"
SITE = "https://www.net-empregos.com"
ANY_ZONE = "todas as zonas"

_TITLE = re.compile(
    r'<h2[^>]*>\s*<a class="oferta-link"[^>]*href\s*=\s*["\']?(/[0-9]+/[^"\'>\s]+)["\']?[^>]*>(.*?)</a>',
    re.I | re.S,
)
_LOCATION = re.compile(r"flaticon-pin[^>]*>\s*</i>\s*([^<]+)", re.I)
_COMPANY = re.compile(r"flaticon-work[^>]*>\s*</i>\s*([^<]+)", re.I)
_COMPANY_ALT = re.compile(r'<img[^>]*alt="([^"]+)"', re.I)
_CATEGORY = re.compile(r"fa-tags[^>]*>\s*</i>\s*([^<]+)", re.I)
_DATE = re.compile(r"flaticon-calendar[^>]*>\s*</i>\s*([^<]+)", re.I)
_POSTED = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


def _posted(value: str):
    match = _POSTED.fullmatch((value or "").strip())
    if not match:
        return None
    day, month, year = match.groups()
    return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)


def _clean(value: str) -> str:
    text = strip_html(html.unescape(value or "")).strip()
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", text))


def parse_jobs(html_text: str) -> list[dict]:
    jobs = []
    seen: set[str] = set()
    for chunk in html_text.split('class="job-item')[1:]:
        title_match = _TITLE.search(chunk)
        if not title_match:
            continue
        path, title = title_match.group(1), _clean(title_match.group(2))
        url = f"{SITE}{path}"
        if url in seen:
            continue
        company_match = _COMPANY.search(chunk) or _COMPANY_ALT.search(chunk)
        location_match = _LOCATION.search(chunk)
        category_match = _CATEGORY.search(chunk)
        date_match = _DATE.search(chunk)
        company = _clean(company_match.group(1)) if company_match else ""
        location = _clean(location_match.group(1) if location_match else "")
        if location.strip("()").casefold() == ANY_ZONE:
            location = ""
        category = _clean(category_match.group(1) if category_match else "")
        posted = _posted(date_match.group(1) if date_match else "")
        built = build_job(
            company=company,
            title=title,
            location=location or "Portugal",
            url=url,
            industry=[category] if category else [],
            excerpt=category,
            source=SOURCE_NAME,
            posted_at=posted,
        )
        if not built:
            continue
        seen.add(url)
        jobs.append(built)
    return jobs


def _collect(query: str, city: str, limit: int) -> list[dict]:
    results = []
    seen_urls: set[str] = set()
    for page in range(1, FEED_PAGES + 1):
        params = {"chaves": query, "page": page}
        if city:
            params["cidade"] = city
        page_jobs = parse_jobs(get_cached_text(API_URL, params, encoding="latin-1"))
        if not page_jobs:
            break
        new_on_page = 0
        for job in page_jobs:
            if job["url"] in seen_urls or not in_requested_city(job.get("location") or "", city, job.get("work_mode")):
                continue
            seen_urls.add(job["url"])
            results.append(job)
            new_on_page += 1
            if len(results) >= limit:
                return take_fresh(results, limit)
        if not new_on_page:
            break
    return take_fresh(results, limit)


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    query = (tag or "").strip()
    if countrywide_portugal(location):
        return _collect(query, "", limit)
    return _collect(query, requested_city(location), limit)
