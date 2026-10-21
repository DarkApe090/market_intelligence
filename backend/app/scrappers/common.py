import html
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx


USER_AGENT = "PontoCareerSearch/1.0"
REQUEST_TIMEOUT = 10
FEED_CACHE_TTL_SECONDS = 600
MAX_JOB_AGE_DAYS = 21
FEED_PAGES = 12

TAG_QUERIES = {
    "software": "software engineer",
    "data": "data",
    "cybersecurity": "security",
    "devops": "devops",
    "design": "designer",
    "marketing": "marketing",
    "finance": "finance",
}

TAG_KEYWORDS = {
    "software": (
        "software", "developer", "engineer", "frontend", "backend", "full stack",
        "fullstack", "programmer", "programador", "desenvolvedor", "desarrollador",
        "engenheiro", "ingeniero",
    ),
    "data": ("data", "dados", "machine learning", "ml", "ai", "analytics", "scientist", "datos"),
    "cybersecurity": ("security", "cyber", "infosec", "pentest", "ciberseguranca", "ciberseguridad"),
    "devops": ("devops", "sre", "reliability", "cloud", "platform", "infrastructure"),
    "design": ("design", "designer", "ux", "ui", "product"),
    "marketing": ("marketing", "seo", "content", "growth", "communications"),
    "finance": ("finance", "financial", "accountant", "accounting", "audit", "financas"),
}

EU_MARKET_HINTS = (
    "portugal", "espanha", "spain", "espana", "europe", "europa", "emea", "eea",
    "lisboa", "lisbon", "porto", "braga", "coimbra", "aveiro", "faro", "madeira",
    "azores", "acores", "madrid", "barcelona", "valencia", "sevilla", "bilbao",
    "france", "paris", "italy", "italia", "milan", "rome", "netherlands", "amsterdam",
    "belgium", "brussels", "ireland", "dublin", "united kingdom", "london",
    "poland", "warsaw", "sweden", "stockholm", "norway", "oslo", "denmark",
    "finland", "austria", "vienna", "switzerland", "zurich", "romania", "greece",
    "czech", "hungary", "slovakia", "slovenia", "croatia", "estonia", "latvia",
    "lithuania", "luxembourg", "malta", "worldwide", "anywhere", "global",
    "schengen",
)

US_ONLY_HINTS = ("usa", "united states", "u.s.a", "u.s.", "america")
DE_ONLY_HINTS = ("germany", "deutschland", "berlin", "munich", "hamburg", "cologne", "frankfurt")
REQUEST_LOCATION_ALIASES = {
    "alemanha": DE_ONLY_HINTS + ("alemanha",),
    "germany": DE_ONLY_HINTS + ("alemanha",),
    "deutschland": DE_ONLY_HINTS + ("alemanha",),
    "franca": ("france", "paris", "franca"),
    "france": ("france", "paris", "franca"),
    "italia": ("italy", "italia", "milan", "rome"),
    "italy": ("italy", "italia", "milan", "rome"),
    "holanda": ("netherlands", "amsterdam", "holland", "holanda"),
    "paises baixos": ("netherlands", "amsterdam", "holland"),
    "netherlands": ("netherlands", "amsterdam", "holland", "holanda"),
    "irlanda": ("ireland", "dublin", "irlanda"),
    "ireland": ("ireland", "dublin", "irlanda"),
    "reino unido": ("united kingdom", "london", "england", "uk"),
}

HYBRID_PATTERN = re.compile(r"\b(?:hybrid|h[ií]brid[oa])\b", re.I)
REMOTE_PATTERN = re.compile(r"\b(?:remote|remot[oa]|teletrabalho|worldwide|anywhere)\b", re.I)
PART_TIME_PATTERN = re.compile(r"\b(?:part[\s-]?time|tempo\s+parcial|meio[\s-]?tempo|parttime)\b", re.I)
FULL_TIME_PATTERN = re.compile(r"\b(?:full[\s-]?time|tempo\s+inteiro|tempo\s+completo|fulltime)\b", re.I)
REGION_ONLY = re.compile(r"^(?:europe|europa|emea|eu|worldwide|anywhere|global|latam|apac)$", re.I)

_feed_cache: dict[str, tuple[float, object]] = {}
_feed_cache_lock = threading.Lock()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized.casefold() if not unicodedata.combining(char))


def http_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> httpx.Response:
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    return httpx.get(
        url,
        params=params,
        headers=merged,
        timeout=timeout,
        follow_redirects=True,
    )


def get_json(url: str, params: dict | None = None, headers: dict | None = None):
    response = http_get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def get_text(url: str, params: dict | None = None, encoding: str | None = None) -> str:
    response = http_get(
        url,
        params=params,
        headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    response.raise_for_status()
    if encoding:
        return response.content.decode(encoding)
    return response.text


def get_cached_json(url: str, params: dict | None = None, headers: dict | None = None):
    cache_key = f"json:{url}?{sorted((params or {}).items())}:{sorted((headers or {}).items())}"
    with _feed_cache_lock:
        cached = _feed_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < FEED_CACHE_TTL_SECONDS:
            return cached[1]

    payload = get_json(url, params, headers)
    with _feed_cache_lock:
        _feed_cache[cache_key] = (time.monotonic(), payload)
    return payload


def get_cached_text(url: str, params: dict | None = None, encoding: str | None = None) -> str:
    cache_key = f"text:{url}:{encoding}?{sorted((params or {}).items())}"
    with _feed_cache_lock:
        cached = _feed_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < FEED_CACHE_TTL_SECONDS:
            return cached[1]

    payload = get_text(url, params, encoding)
    with _feed_cache_lock:
        _feed_cache[cache_key] = (time.monotonic(), payload)
    return payload


def strip_html(value: str | None, max_length: int = 1500) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:max_length]


def matches_tag(tag: str, text: str) -> bool:
    keywords = TAG_KEYWORDS.get(tag.casefold())
    if not keywords:
        keywords = tuple(part for part in re.findall(r"[A-Za-zÀ-ÿ0-9+#.]{3,}", tag))
        if not keywords:
            return True
    pattern = r"\b(?:" + "|".join(re.escape(keyword) for keyword in keywords) + r")\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def parse_posted_at(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        posted = value
    elif isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        posted = datetime.fromtimestamp(int(value), tz=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        try:
            posted = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            try:
                posted = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted.astimezone(timezone.utc)


def is_fresh(posted_at: datetime | None, max_age_days: int = MAX_JOB_AGE_DAYS) -> bool:
    if posted_at is None:
        return True
    return (datetime.now(timezone.utc) - posted_at).days <= max_age_days


COUNTRY_CANON = {
    "portugal": "portugal", "pt": "portugal",
    "spain": "spain", "espanha": "spain", "espana": "spain", "es": "spain",
    "germany": "germany", "alemanha": "germany", "deutschland": "germany",
    "france": "france", "franca": "france",
    "italy": "italy", "italia": "italy",
    "netherlands": "netherlands", "holanda": "netherlands", "paises baixos": "netherlands",
    "ireland": "ireland", "irlanda": "ireland",
    "united kingdom": "united kingdom", "reino unido": "united kingdom", "uk": "united kingdom",
}


COUNTRY_LOCATION_LABELS = {
    "portugal", "pt", "espanha", "spain", "espana", "europe", "europa",
    "alemanha", "germany", "deutschland", "france", "franca", "italy", "italia",
}


def countrywide_portugal(location: str) -> bool:
    _place, country, is_country = requested_scope(location)
    return is_country and country == "portugal"


def requested_city(location: str) -> str:
    place, _country, is_country = requested_scope(location)
    if is_country or place in COUNTRY_LOCATION_LABELS:
        return ""
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    return parts[0] if parts else ""


def in_requested_city(job_location: str, city: str, work_mode: str | None = None) -> bool:
    if not city:
        return True
    if work_mode == "remote":
        return True
    folded = _fold(job_location or "")
    if not folded or folded in COUNTRY_LOCATION_LABELS:
        return True
    needle = _fold(city)
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", folded))


def requested_scope(location: str) -> tuple[str, str, bool]:
    """(sítio, país, pesquisa de país). 'Braga, Portugal' é cidade; 'Portugal' é o país."""
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    if not parts:
        return "", "", False
    folded = [_fold(part) for part in parts]
    if folded[-1] in COUNTRY_CANON:
        country = COUNTRY_CANON[folded[-1]]
        place = folded[0]
        return place, country, place in COUNTRY_CANON and COUNTRY_CANON[place] == country
    place = folded[0]
    if place in COUNTRY_CANON:
        return place, COUNTRY_CANON[place], True
    return place, "", False


def is_european_market(*parts: str, requested: str = "") -> bool:
    blob = _fold(" ".join(part or "" for part in parts))
    req = _fold(requested)
    us_only = any(hint in blob for hint in US_ONLY_HINTS) and not any(hint in blob for hint in EU_MARKET_HINTS)
    if req:
        hints = (req, *REQUEST_LOCATION_ALIASES.get(req, ()))
        if any(hint in blob for hint in hints if len(hint) > 2):
            return True
        if REMOTE_PATTERN.search(blob) and not us_only:
            return True
    if any(hint in blob for hint in EU_MARKET_HINTS) or re.search(r"\b(?:eu|uk|pt|es)\b", blob):
        return True
    if any(hint in blob for hint in US_ONLY_HINTS + DE_ONLY_HINTS):
        return False
    return False


def rss_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        def child(tag: str) -> str:
            node = item.find(tag)
            return (node.text or "").strip() if node is not None else ""

        items.append(
            {
                "title": child("title"),
                "link": child("link") or child("guid"),
                "description": child("description"),
                "pubDate": child("pubDate"),
                "region": child("region"),
                "category": child("category"),
            }
        )
    return items


def rss_description_field(description: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*(.+?)(?:<br\s*/?>|$)", description or "", flags=re.I)
    value = strip_html(match.group(1) if match else "")
    return "" if value.casefold() in {"n/d", "n.d.", "nd"} else value


def work_mode(title: str, location: str) -> str | None:
    """Só título e local: a descrição fala de "remote" por outros motivos."""
    text = f"{title} {location}"
    if HYBRID_PATTERN.search(text):
        return "hybrid"
    if REMOTE_PATTERN.search(text) or REGION_ONLY.fullmatch((location or "").strip()):
        return "remote"
    return "onsite" if title or location else None


def normalize_schedule(*parts: str) -> str | None:
    keys = [part for part in parts if part in {"full_time", "part_time"}]
    text = " ".join(part for part in parts if part)
    if PART_TIME_PATTERN.search(text):
        return "part_time"
    if FULL_TIME_PATTERN.search(text):
        return "full_time"
    return keys[0] if keys else None


def take_fresh(jobs: list[dict], limit: int) -> list[dict]:
    fresh = [job for job in jobs if job and is_fresh(job.get("posted_at"))]
    fresh.sort(key=lambda job: job.get("posted_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return fresh[:limit]


def build_job(
    *,
    company: str | None,
    title: str | None,
    location: str | None,
    url: str | None,
    industry: list[str] | None,
    excerpt: str | None,
    source: str,
    posted_at=None,
    rating: float | None = None,
    review_count: int | None = None,
    salary: str | None = None,
    seniority: str | None = None,
    company_url: str | None = None,
    schedule: str | None = None,
    contract: str | None = None,
) -> dict | None:
    company = (company or "").strip()
    title = (title or "").strip()
    url = (url or "").strip()
    location = (location or "").strip()
    if not company or not title or not url:
        return None
    hours = normalize_schedule(schedule or "", title)
    job = {
        "company": company,
        "title": title,
        "location": location,
        "work_mode": work_mode(title, location),
        "url": url,
        "industry": [item for item in (industry or []) if item and normalize_schedule(item) is None],
        "excerpt": strip_html(excerpt),
        "source": source,
        "posted_at": parse_posted_at(posted_at),
    }
    if rating is not None:
        job["rating"] = rating
    if review_count is not None:
        job["review_count"] = review_count
    if salary:
        job["salary"] = salary
    if seniority:
        job["seniority"] = seniority
    if company_url:
        job["company_url"] = company_url
    if hours:
        job["schedule"] = hours
    if contract:
        job["contract"] = contract
    return job
