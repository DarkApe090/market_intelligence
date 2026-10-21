import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from app.scrappers.common import (
    FEED_PAGES,
    TAG_QUERIES,
    _fold,
    build_job,
    countrywide_portugal,
    get_cached_json,
    get_cached_text,
    in_requested_city,
    is_fresh,
    requested_city,
    requested_scope,
    strip_html,
    take_fresh,
)


API_URL = "https://pt.teamlyzer.com/companies/jobs"
SITE = "https://pt.teamlyzer.com"
SOURCE_NAME = "Teamlyzer"
_CITY_ALIASES = {"lisbon": "lisboa", "oporto": "porto"}
_TITLE = re.compile(
    r'class="jobcard__title-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_COMPANY = re.compile(r'class="jobcard__company"[^>]*>(.*?)</a>', re.I | re.S)
_COMPANY_HREF = re.compile(
    r'<a[^>]*class="jobcard__company"[^>]*href="([^"]+)"|<a[^>]*href="([^"]+)"[^>]*class="jobcard__company"',
    re.I,
)
_LOCATION = re.compile(r'class="jobcard__location"[^>]*>.*?</i>\s*([^<]+)', re.I | re.S)
_ON_SITE = re.compile(r'class="jobcard__on-site"[^>]*title="([^"]*)"', re.I)
_RATING = re.compile(r'class="jobcard__rating"[^>]*>.*?</i>\s*([0-9]+(?:\.[0-9]+)?)', re.I | re.S)
_REVIEWS = re.compile(r'class="jobcard__reviews"[^>]*>\s*(\d+)\s*Reviews', re.I)
_SALARY = re.compile(r'class="jobcard__salary"[^>]*>\s*(€[^<]+)', re.I)
_SENIORITY = re.compile(r'class="jobcard__seniority"[^>]*>.*?</i>\s*([^<]+)', re.I | re.S)
_TAG = re.compile(r'class="role-tag[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
_RELATIVE = re.compile(r"ha\s+(\d+)\s+(dia|dias|semana|semanas|mes|meses)")


def _address(location: str) -> str:
    city = requested_city(location)
    if not city:
        return ""
    place, _country, _is_country = requested_scope(location)
    return _CITY_ALIASES.get(place, place)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", strip_html(html.unescape(value or ""))).strip()


def _posted(value: str):
    folded = _fold(value)
    if not folded:
        return None
    if "nova" in folded:
        return datetime.now(timezone.utc)
    match = _RELATIVE.search(folded)
    if not match:
        return None
    count = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("dia"):
        delta = timedelta(days=count)
    elif unit.startswith("semana"):
        delta = timedelta(weeks=count)
    else:
        delta = timedelta(days=30 * count)
    return datetime.now(timezone.utc) - delta


def parse_jobs(html_text: str) -> list[dict]:
    jobs = []
    seen: set[str] = set()
    for chunk in html_text.split('<div class="panel jobcard">')[1:]:
        title_match = _TITLE.search(chunk)
        if not title_match:
            continue
        path, title = title_match.group(1), _clean(title_match.group(2))
        url = path if path.startswith("http") else f"{SITE}{path}"
        if url in seen:
            continue
        company_match = _COMPANY.search(chunk)
        href_match = _COMPANY_HREF.search(chunk)
        location_match = _LOCATION.search(chunk)
        tag_match = _TAG.search(chunk)
        on_site_match = _ON_SITE.search(chunk)
        rating_match = _RATING.search(chunk)
        reviews_match = _REVIEWS.search(chunk)
        salary_match = _SALARY.search(chunk)
        seniority_match = _SENIORITY.search(chunk)
        company = _clean(company_match.group(1) if company_match else "")
        location_raw = _clean(location_match.group(1) if location_match else "")
        location = re.sub(r"\s*\([^)]*\)\s*$", "", location_raw).strip() or location_raw
        tag = _clean(tag_match.group(1) if tag_match else "")
        company_path = (href_match.group(1) or href_match.group(2) or "") if href_match else ""
        company_url = (
            company_path if company_path.startswith("http") else f"{SITE}{company_path}"
        ) if company_path else None
        built = build_job(
            company=company,
            title=title,
            location=location_raw or "Portugal",
            url=url,
            industry=[tag] if tag else [],
            excerpt=tag,
            source=SOURCE_NAME,
            posted_at=_posted(on_site_match.group(1) if on_site_match else ""),
            rating=float(rating_match.group(1)) if rating_match else None,
            review_count=int(reviews_match.group(1)) if reviews_match else None,
            salary=_clean(salary_match.group(1)) if salary_match else None,
            seniority=_clean(seniority_match.group(1)) if seniority_match else None,
            company_url=company_url,
        )
        if not built:
            continue
        if location:
            built["location"] = location
        seen.add(url)
        jobs.append(built)
    return jobs


def _collect(address: str, query: str, city: str, limit: int) -> list[dict]:
    results = []
    seen_urls: set[str] = set()
    for page in range(1, FEED_PAGES + 1):
        params = {"page": page, "order": "most_recent"}
        if address:
            params["address"] = address
        if query:
            params["q"] = query
        page_jobs = parse_jobs(get_cached_text(API_URL, params))
        if not page_jobs:
            break
        new_on_page = 0
        for job in page_jobs:
            if job["url"] in seen_urls or not in_requested_city(job.get("location") or "", city, job.get("work_mode")):
                continue
            if not is_fresh(job.get("posted_at")):
                continue
            seen_urls.add(job["url"])
            results.append(job)
            new_on_page += 1
            if len(results) >= limit:
                return take_fresh(results, limit)
        if not new_on_page:
            break
    return take_fresh(results, limit)


def _query_name(name: str) -> str:
    return re.split(r"\s+[-–—|]\s+", name.strip(), maxsplit=1)[0].strip()


def _pick_company(name: str, results: list[dict]) -> dict | None:
    target = _fold(_query_name(name))
    if len(target) < 2:
        return None
    ranked = []
    for item in results:
        other = _fold(item.get("name") or "")
        if not other:
            continue
        if other == target:
            return item
        if target.startswith(other) or other.startswith(target):
            ranked.append(item)
    return ranked[0] if len(ranked) == 1 else None


def lookup_company(name: str) -> dict | None:
    query = _query_name(name)
    if len(query) < 2:
        return None
    try:
        payload = get_cached_json(f"{SITE}/users/autocomplete_company/v2/{quote(query)}")
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    match = _pick_company(query, payload.get("results") or [])
    if not match or not match.get("rating"):
        return None
    reviews = int(match.get("reviews_job") or 0) + int(match.get("reviews_interview") or 0)
    intel = {"rating": float(match["rating"])}
    if reviews:
        intel["review_count"] = reviews
    if match.get("slug"):
        intel["company_url"] = f"{SITE}/companies/{match['slug']}"
    return intel


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    if countrywide_portugal(location):
        return _collect("", "", "", limit)
    city = requested_city(location)
    address = _address(location)
    query = "" if address else TAG_QUERIES.get(tag, tag)
    return _collect(address, query, city, limit)
