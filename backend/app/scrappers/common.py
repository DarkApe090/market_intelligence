import html
import re
import threading
import time

import httpx


USER_AGENT = "PontoCareerSearch/1.0"
REQUEST_TIMEOUT = 20
FEED_CACHE_TTL_SECONDS = 600

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
    "software": ("software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack", "programmer"),
    "data": ("data", "machine learning", "ml", "ai", "analytics", "scientist"),
    "cybersecurity": ("security", "cyber", "infosec", "pentest"),
    "devops": ("devops", "sre", "reliability", "cloud", "platform", "infrastructure"),
    "design": ("design", "designer", "ux", "ui", "product"),
    "marketing": ("marketing", "seo", "content", "growth", "communications"),
    "finance": ("finance", "financial", "accountant", "accounting", "audit"),
}

_feed_cache: dict[str, tuple[float, object]] = {}
_feed_cache_lock = threading.Lock()


def get_json(url: str, params: dict | None = None):
    response = httpx.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def get_cached_json(url: str, params: dict | None = None):
    cache_key = f"{url}?{sorted((params or {}).items())}"
    with _feed_cache_lock:
        cached = _feed_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < FEED_CACHE_TTL_SECONDS:
            return cached[1]

    payload = get_json(url, params)
    with _feed_cache_lock:
        _feed_cache[cache_key] = (time.monotonic(), payload)
    return payload


def strip_html(value: str | None, max_length: int = 1500) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:max_length]


def matches_tag(tag: str, text: str) -> bool:
    keywords = TAG_KEYWORDS.get(tag)
    if not keywords:
        return True
    pattern = r"\b(?:" + "|".join(re.escape(keyword) for keyword in keywords) + r")\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def build_job(
    *,
    company: str | None,
    title: str | None,
    location: str | None,
    url: str | None,
    industry: list[str] | None,
    excerpt: str | None,
    source: str,
) -> dict | None:
    company = (company or "").strip()
    title = (title or "").strip()
    url = (url or "").strip()
    if not company or not title or not url:
        return None
    return {
        "company": company,
        "title": title,
        "location": (location or "").strip(),
        "url": url,
        "industry": industry or [],
        "excerpt": strip_html(excerpt),
        "source": source,
    }
