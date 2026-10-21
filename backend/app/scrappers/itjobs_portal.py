import re

from app.scrappers.common import (
    COUNTRY_LOCATION_LABELS,
    FEED_PAGES,
    TAG_QUERIES,
    _fold,
    build_job,
    countrywide_portugal,
    get_cached_text,
    is_european_market,
    requested_scope,
    rss_description_field,
    rss_items,
    take_fresh,
)


API_URL = "http://feeds.itjobs.pt/feed/ofertas/"
SOURCE_NAME = "ITJobs"
_SKIP_PLACES = COUNTRY_LOCATION_LABELS | {
    "remote", "remoto", "internacional", "international", "worldwide",
}
_LOCATION_ID_RE = re.compile(r'href="/emprego\?location=(\d+)" title="([^"]+)"')
_PLACES: list[tuple[str, str, str]] | None = None


def _places() -> list[tuple[str, str, str]]:
    """(nome dobrado, nome no board, id ITJobs)."""
    global _PLACES
    if _PLACES is not None:
        return _PLACES
    page = get_cached_text("https://www.itjobs.pt/ofertas")
    places = []
    seen_ids: set[str] = set()
    for loc_id, name in _LOCATION_ID_RE.findall(page):
        folded = _fold(name)
        if folded in _SKIP_PLACES or loc_id in seen_ids:
            continue
        seen_ids.add(loc_id)
        places.append((folded, name.strip(), loc_id))
    _PLACES = places
    return _PLACES


def _location_ids() -> dict[str, str]:
    return {folded: loc_id for folded, _name, loc_id in _places()}


def _location_id(location: str) -> str | None:
    place, country, is_country = requested_scope(location)
    if is_country or country not in {"", "portugal"}:
        return None
    return _location_ids().get(place)


def _collect(query: str, loc_id: str | None, location: str, limit: int) -> list[dict]:
    results = []
    seen_urls: set[str] = set()
    for page in range(1, FEED_PAGES + 1):
        params = {"page": page}
        if query:
            params["q"] = query
        if loc_id:
            params["location"] = loc_id
        xml_text = get_cached_text(API_URL, params)
        items = rss_items(xml_text)
        if not items:
            break
        new_on_page = 0
        for item in items:
            description = item["description"]
            job_location = rss_description_field(description, "Localidade") or "Portugal"
            if not is_european_market(job_location, requested=location):
                continue
            schedule = rss_description_field(description, "Tipo")
            contract = rss_description_field(description, "Contrato")
            built = build_job(
                company=rss_description_field(description, "Empresa"),
                title=item["title"],
                location=job_location,
                url=item["link"],
                industry=[schedule] if schedule else [],
                excerpt=" · ".join(value for value in (schedule, contract) if value),
                source=SOURCE_NAME,
                posted_at=item["pubDate"],
                schedule=schedule or None,
                contract=contract or None,
            )
            if not built or built["url"] in seen_urls:
                continue
            seen_urls.add(built["url"])
            results.append(built)
            new_on_page += 1
            if len(results) >= limit:
                return take_fresh(results, limit)
        if not new_on_page:
            break
    return take_fresh(results, limit)


def search_jobs(tag: str, location: str, limit: int = 10) -> list[dict]:
    if countrywide_portugal(location):
        return _collect("", None, "Portugal", limit)
    loc_id = _location_id(location)
    query = "" if loc_id else TAG_QUERIES.get(tag, tag)
    return _collect(query, loc_id, location, limit)
