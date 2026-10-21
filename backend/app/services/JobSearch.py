from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import re

from app.scrappers.common import DE_ONLY_HINTS, EU_MARKET_HINTS, US_ONLY_HINTS, normalize_schedule, requested_scope
from app.scrappers.teamlyzer_portal import lookup_company
from app.scrappers.email_finder import emails_matching_company, pick_contact_email
from app.scrappers.job_sources import iter_source_results
from app.services.CareerProfile import (
    MAX_CV_BYTES,
    MAX_SEARCH_AREAS,
    STOPWORDS,
    _has_term,
    _normalize,
    _profile_from_stored,
    _tokens,
    extract_cv_text,
    extract_profile,
)


JOBS_PER_AREA = 80
SUMMARY_LENGTH = 320
LOCATION_PRIORITY_ORDER = [
    "Localização exata",
    "Também elegível na localização escolhida",
    "Região compatível",
    "Remoto/global",
    "Localização por confirmar",
]
_COMPANY_LEGAL = re.compile(r",?\s*\b(?:lda|l da|s a|sa|ltd|inc|gmbh)\.?$")
REQUIREMENT_NOISE = {
    "speaker", "speakers", "speaking", "falante", "falantes", "native", "nativo",
    "nativa", "fluent", "fluente", "and", "the",
}
WEAK_ROLE_TOKENS = {
    "senior", "junior", "intern", "estagio", "lead", "principal", "staff",
    "manager", "assistant", "consultant", "analyst", "specialist",
    "engineer", "engenheiro", "engenheira", "ingeniero", "ingeniera",
    "engenharia", "engineering",
}
PORTUGAL_PLACES = {
    "portugal", "pt", "lisboa", "lisbon", "porto", "braga", "coimbra", "aveiro",
    "faro", "madeira", "azores", "acores", "setubal", "leiria", "viseu",
    "santarem", "evora", "beja", "guarda", "castelo branco", "braganca",
    "viana do castelo", "vila real", "portalegre",
}
SPAIN_PLACES = {
    "spain", "espanha", "espana", "es", "madrid", "barcelona", "valencia",
    "sevilla", "bilbao", "malaga", "zaragoza",
}
GERMANY_PLACES = set(DE_ONLY_HINTS) | {"alemanha", "munchen", "koln", "dusseldorf", "stuttgart"}
COUNTRY_CITIES = {
    "portugal": PORTUGAL_PLACES,
    "spain": SPAIN_PLACES,
    "germany": GERMANY_PLACES,
}
COUNTRY_TOKENS = {
    "portugal": {"portugal", "pt"},
    "spain": {"spain", "espanha", "espana", "es"},
    "germany": {"germany", "alemanha", "deutschland", "de"},
    "france": {"france", "franca"},
    "italy": {"italy", "italia"},
    "netherlands": {"netherlands", "holland", "holanda"},
    "ireland": {"ireland", "irlanda"},
    "united kingdom": {"uk", "united kingdom", "england", "britain"},
    "united states": {"usa", "united states", "united states of america", "us", "america"},
}
REGION_COUNTRIES = {
    "europe": {
        "albania", "andorra", "austria", "belarus", "belgium", "bosnia",
        "bulgaria", "croatia", "cyprus", "czechia", "denmark", "estonia",
        "finland", "france", "germany", "greece", "hungary", "iceland",
        "ireland", "italy", "kosovo", "latvia", "liechtenstein", "lithuania",
        "luxembourg", "malta", "moldova", "monaco", "montenegro", "netherlands",
        "north macedonia", "norway", "poland", "portugal", "romania", "san marino",
        "serbia", "slovakia", "slovenia", "spain", "sweden", "switzerland",
        "uk", "ukraine", "united kingdom", "vatican city", "pt",
    },
    "emea": {"europe", "middle east", "africa", "portugal", "pt"},
    "eu": {"europe", "portugal", "pt"},
}
WORK_MODE_FILTERS = {"", "all", "onsite", "hybrid", "remote"}
SCHEDULE_FILTERS = {"", "all", "full_time", "part_time"}
REMOTE_LOCATIONS = {
    "remote", "remoto", "worldwide", "global", "anywhere", "remote worldwide",
    "hybrid", "hibrido", "teletrabalho",
}
KNOWN_LOCATIONS = {
    "argentina", "australia", "brazil", "brasil", "canada", "china", "india",
    "japan", "mexico", "new zealand", "singapore", "south korea", "usa",
    "united states", "united states of america", "portugal", "pt", "lisbon",
    "lisboa", "porto", "braga", "coimbra", "aveiro", "faro", "madeira",
    "azores", "acores", "europe", "emea", "eu", "latam", "latin america",
    "north america", "apac", "asia pacific", "middle east", "africa", "uk",
    "united kingdom", "spain", "espanha", "espana", "france", "germany",
    "netherlands", "ireland", "madrid", "barcelona", "valencia", "sevilla",
    "setubal", "leiria",
}
KNOWN_PLACES = KNOWN_LOCATIONS | set(EU_MARKET_HINTS) | set(US_ONLY_HINTS) | set(DE_ONLY_HINTS)


def uses_remote_boards(work_mode: str) -> bool:
    return work_mode not in {"onsite", "hybrid"}


def _clean_choice(value: str | None, allowed: set[str]) -> str:
    text = (value or "").strip()
    if text == "all":
        return ""
    return text if text in allowed else ""


def fetch_source_batches(
    tag: str, location: str, limit: int = JOBS_PER_AREA, include_remote: bool = True,
):
    yield from iter_source_results(tag, location, limit, include_remote)


def _company_key(name: str) -> str:
    folded = _normalize(name)
    folded = re.split(r"\s+[-–—|]\s+", folded, maxsplit=1)[0]
    return _COMPANY_LEGAL.sub("", folded).strip()


def _place_bucket(location: str, work_mode: str | None) -> str:
    if work_mode == "remote":
        return "remote"
    parts = [
        _normalize(part)
        for part in re.split(r"[,;/|()]", location or "")
        if _normalize(part) and _normalize(part) != "regime"
    ]
    return parts[0] if parts else ""


def _requirement_words(chunk: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z]+", _normalize(chunk))
        if len(word) >= 3 and word not in REQUIREMENT_NOISE and word not in STOPWORDS
    ]


def _spoken_requirements(title: str) -> list[str]:
    """Idiomas exigidos no título (French Speaker, falante de francês, German-speaking)."""
    text = _normalize(title)
    found: list[str] = []
    for chunk in re.findall(r"\(([^)]+)\)", text):
        if re.search(r"\b(?:speaker|falante|speaking)\b", chunk):
            found.extend(_requirement_words(chunk))
    found.extend(re.findall(r"\b([a-z]+)-speaking\b", text))
    for match in re.finditer(r"\bfalante(?:s)?\s+de\s+([a-z]+(?:\s+e\s+[a-z]+)?)\b", text):
        found.extend(_requirement_words(match.group(1)))
    for match in re.finditer(
        r"\b(?:native|nativo(?:a)?(?:\s+de|\s+em)?|fluent(?:e)?(?:\s+(?:in|em))?)\s+([a-z]+)\b",
        text,
    ):
        found.extend(_requirement_words(match.group(1)))
    return [word for word in dict.fromkeys(found) if word not in REQUIREMENT_NOISE]


def _distinctive_tokens(area: dict) -> list[str]:
    weak = WEAK_ROLE_TOKENS | STOPWORDS
    tokens = []
    for source in (area.get("name"), area.get("search_tag"), *(area.get("role_terms") or [])):
        tokens.extend(_tokens(source or ""))
    return [token for token in dict.fromkeys(tokens) if _normalize(token) not in weak]


def _home_places(country: str, place: str, is_country: bool) -> set[str]:
    tokens = COUNTRY_TOKENS.get(country, {country} if country else set()) | ({place} if place else set())
    if is_country:
        tokens |= COUNTRY_CITIES.get(country, set())
    return tokens


def _other_places(country: str, place: str, is_country: bool) -> set[str]:
    home = _home_places(country, place, is_country)
    extra = set()
    for name, tokens in COUNTRY_TOKENS.items():
        if name != country:
            extra |= tokens
    for name, cities in COUNTRY_CITIES.items():
        if name != country or not is_country:
            extra |= cities
    return (KNOWN_PLACES | extra) - home - set(REGION_COUNTRIES) - REMOTE_LOCATIONS


def _location_priority(job_location: str, requested_location: str, work_mode: str | None = None) -> int | None:
    location_parts = {
        _normalize(part)
        for part in re.split(r"[,;/|()]", job_location)
        if _normalize(part) and _normalize(part) != "regime"
    }
    if not location_parts:
        return 4

    place, country, is_country = requested_scope(requested_location)
    if not country and place in COUNTRY_CITIES.get("portugal", set()):
        country = "portugal"
    home = _home_places(country, place, is_country)
    foreign = location_parts.intersection(_other_places(country, place, is_country))
    remote_match = work_mode == "remote" or bool(location_parts.intersection(REMOTE_LOCATIONS))
    region_matches = any(
        region in location_parts and (not country or country in countries or place in countries)
        for region, countries in REGION_COUNTRIES.items()
    )

    if place and place in location_parts:
        return 0 if not foreign else 1

    other_countries = set()
    for name, tokens in COUNTRY_TOKENS.items():
        if name != country:
            other_countries |= tokens
    if remote_match and not location_parts.intersection(other_countries):
        return 3

    if is_country:
        if location_parts.intersection(home):
            return 0 if not foreign else 1
        if foreign:
            return None
        if region_matches:
            return 2
        return 0

    country_tokens = COUNTRY_TOKENS.get(country, set())
    if foreign:
        return None
    if location_parts.intersection(country_tokens) or region_matches:
        return 2
    return None


def _summary(text: str) -> str:
    if len(text) <= SUMMARY_LENGTH:
        return text
    return text[:SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"


def _match_job(
    job: dict,
    area: dict,
    location: str,
    cv_skills: list[str],
    excluded: set[str],
    cv_text: str,
    work_mode: str = "",
    schedule: str = "",
) -> tuple[dict | None, str | None, bool]:
    """Devolve (sugestão, empresa já na lista, localização excluída)."""
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    url = (job.get("url") or "").strip()
    job_location = (job.get("location") or "").strip()
    if not company or not title or not url:
        return None, None, False

    company_key = _company_key(company)
    if company_key in excluded:
        return None, company_key, False

    job_mode = job.get("work_mode")
    location_priority = _location_priority(job_location, location, job_mode)
    if location_priority is None:
        return None, None, True
    if work_mode == "onsite" and (job_mode in {"remote", "hybrid"} or location_priority == 3):
        return None, None, True
    if work_mode == "hybrid" and job_mode != "hybrid":
        return None, None, True
    if work_mode == "remote" and job_mode != "remote" and location_priority != 3:
        return None, None, True
    hours = normalize_schedule(job.get("schedule") or "", title)
    if schedule in {"full_time", "part_time"} and hours != schedule:
        return None, None, False

    cv_normalized = _normalize(cv_text)
    missing_language = next(
        (word for word in _spoken_requirements(title) if not _has_term(cv_normalized, word)),
        None,
    )
    if missing_language:
        return None, None, False

    normalized_title = _normalize(title)
    normalized_industries = [_normalize(item) for item in job.get("industry", [])]
    normalized_excerpt = _normalize(job.get("excerpt") or "")
    searchable_text = " ".join([normalized_title, *normalized_industries, normalized_excerpt])
    phrases = [
        term for term in (area.get("name"), area.get("search_tag"), *(area.get("role_terms") or [area["name"]]))
        if isinstance(term, str) and term.strip()
    ]
    role_matches = [
        term for term in phrases
        if _has_term(normalized_title, term) or _has_term(searchable_text, term)
    ]
    token_matches = [token for token in _distinctive_tokens(area) if _has_term(searchable_text, token)]
    skill_matches = [skill for skill in cv_skills if _has_term(searchable_text, skill)]
    title_skill_matches = [skill for skill in skill_matches if _has_term(normalized_title, skill)]
    industry_match = any(
        _normalize(industry) in job_industry
        for industry in area.get("industries") or []
        for job_industry in normalized_industries
    )
    if not role_matches and not token_matches and not title_skill_matches and not industry_match:
        return None, None, False

    suggestion = {
        "company": company,
        "title": title,
        "location": job_location or "Localização não confirmada",
        "work_mode": job_mode,
        "posted_at": job["posted_at"].isoformat() if job.get("posted_at") else None,
        "summary": _summary(job.get("excerpt") or ""),
        "email": pick_contact_email(emails_matching_company(job.get("excerpt") or "", company), company),
        "location_priority": location_priority,
        "url": url,
        "area": area["name"],
        "source": job.get("source", "Desconhecida"),
        "matched_skills": skill_matches,
        "match_score": (
            len(role_matches) * 4
            + len(token_matches) * 3
            + len(title_skill_matches) * 3
            + len(skill_matches) * 2
            + (2 if industry_match else 0)
        ),
    }
    for key in ("rating", "review_count", "salary", "seniority", "company_url", "contract"):
        if job.get(key) is not None:
            suggestion[key] = job[key]
    if hours:
        suggestion["schedule"] = hours
    tags = [
        item for item in job.get("industry") or []
        if item and item != hours and normalize_schedule(item) is None
    ]
    if tags:
        suggestion["tags"] = tags
    return suggestion, None, False


def _copy_known_reviews(by_card: dict) -> None:
    known: dict[str, dict] = {}
    for suggestion in by_card.values():
        if suggestion.get("rating") is None:
            continue
        known.setdefault(_company_key(suggestion["company"]), {
            key: suggestion[key]
            for key in ("rating", "review_count", "company_url")
            if suggestion.get(key) is not None
        })
    for suggestion in by_card.values():
        intel = known.get(_company_key(suggestion["company"]))
        if not intel:
            continue
        for key, value in intel.items():
            suggestion.setdefault(key, value)


def _fill_company_reviews(by_card: dict) -> None:
    _copy_known_reviews(by_card)
    missing: list[str] = []
    seen: set[str] = set()
    for suggestion in by_card.values():
        if suggestion.get("rating") is not None:
            continue
        key = _company_key(suggestion["company"])
        if key in seen:
            continue
        seen.add(key)
        missing.append(suggestion["company"])
    if not missing:
        return
    found: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(missing))) as pool:
        futures = {pool.submit(lookup_company, name): name for name in missing[:32]}
        for future in as_completed(futures):
            try:
                intel = future.result()
            except Exception:
                continue
            if intel:
                found[_company_key(futures[future])] = intel
    for suggestion in by_card.values():
        intel = found.get(_company_key(suggestion["company"]))
        if not intel:
            continue
        for key, value in intel.items():
            suggestion.setdefault(key, value)


def _ranked_companies(by_card: dict) -> list[dict]:
    return sorted(
        by_card.values(),
        key=lambda suggestion: (suggestion["location_priority"], -suggestion["match_score"]),
    )


def fold_analysis(events: list[dict]) -> dict:
    result = {
        "candidate_name": None,
        "areas": [],
        "llm_used": False,
        "suggestions": [],
        "location_priority_order": LOCATION_PRIORITY_ORDER,
        "excluded_location_count": 0,
        "already_in_list_count": 0,
        "search_errors": [],
        "cv_saved": False,
    }
    for event in events:
        kind = event.get("type")
        if kind == "error":
            raise ValueError(event.get("detail") or "Análise falhou.")
        if kind == "profile":
            result["candidate_name"] = event.get("candidate_name")
            result["areas"] = event.get("areas") or []
            result["llm_used"] = bool(event.get("llm_used"))
            if "cv_saved" in event:
                result["cv_saved"] = event["cv_saved"]
            if event.get("location_priority_order"):
                result["location_priority_order"] = event["location_priority_order"]
        elif kind == "jobs":
            result["suggestions"] = event.get("suggestions") or []
        elif kind == "done":
            result["search_errors"] = event.get("search_errors") or []
            result["already_in_list_count"] = event.get("already_in_list_count") or 0
            result["excluded_location_count"] = event.get("excluded_location_count") or 0
    return result


def analyze_cv_stream(
    filename: str,
    content: bytes,
    location: str = "Portugal",
    exclude_companies: list[str] | None = None,
    saved_urls: list[str] | None = None,
    profile: dict | None = None,
    work_mode: str = "",
    schedule: str = "",
):
    if len(content) > MAX_CV_BYTES:
        raise ValueError("O CV excede o limite de 5 MB.")

    text = extract_cv_text(filename, content)
    stored = _profile_from_stored(profile)
    if stored:
        candidate_name, areas, llm_used, languages = stored
    else:
        candidate_name, areas, llm_used, languages = extract_profile(text)
    yield {
        "type": "profile",
        "candidate_name": candidate_name,
        "areas": areas,
        "languages": languages,
        "llm_used": llm_used,
        "location_priority_order": LOCATION_PRIORITY_ORDER,
    }

    work_mode = _clean_choice(work_mode, WORK_MODE_FILTERS)
    schedule = _clean_choice(schedule, SCHEDULE_FILTERS)
    include_remote = uses_remote_boards(work_mode)
    cv_skills = list(dict.fromkeys(skill for area in areas for skill in area["matched_skills"]))
    cv_blob = " ".join([text, *languages])
    excluded = {_company_key(name) for name in exclude_companies or []}
    known_urls = {url.strip().casefold() for url in saved_urls or [] if url and url.strip()}
    search_areas = areas[:MAX_SEARCH_AREAS]
    listed_hits: set[str] = set()
    excluded_location_count = 0
    search_errors: list[str] = []
    seen_jobs: set[tuple[str, str]] = set()
    by_card: dict[tuple[str, str], dict] = {}

    incoming: Queue = Queue()

    def worker(area: dict) -> None:
        tag = _normalize(area.get("name") or area.get("search_tag") or "")
        try:
            for source_name, jobs in fetch_source_batches(
                tag, location, JOBS_PER_AREA, include_remote=include_remote,
            ):
                incoming.put(("batch", area, source_name, jobs))
        finally:
            incoming.put(("area_done", area, None, None))

    with ThreadPoolExecutor(max_workers=max(len(search_areas), 1)) as pool:
        for area in search_areas:
            pool.submit(worker, area)

        finished = 0
        while finished < len(search_areas):
            kind, area, source_name, jobs = incoming.get()
            if kind == "area_done":
                finished += 1
                continue
            if jobs is None:
                search_errors.append(f"{area['name']} ({source_name})")
                continue

            changed = False
            for job in jobs:
                suggestion, listed, bad_location = _match_job(
                    job, area, location, cv_skills, excluded, cv_blob, work_mode, schedule,
                )
                if listed:
                    listed_hits.add(listed)
                    continue
                if bad_location:
                    excluded_location_count += 1
                    continue
                if suggestion is None:
                    continue
                if suggestion["url"].casefold() in known_urls:
                    continue
                job_key = (suggestion["company"].casefold(), suggestion["url"])
                if job_key in seen_jobs:
                    continue
                seen_jobs.add(job_key)
                card_key = (
                    _company_key(suggestion["company"]),
                    _place_bucket(suggestion["location"], suggestion.get("work_mode")),
                )
                current = by_card.get(card_key)
                if current is None or (suggestion["location_priority"], -suggestion["match_score"]) < (
                    current["location_priority"],
                    -current["match_score"],
                ):
                    by_card[card_key] = suggestion
                    changed = True
            if changed:
                yield {"type": "jobs", "suggestions": _ranked_companies(by_card)}

    if by_card:
        _fill_company_reviews(by_card)
        yield {"type": "jobs", "suggestions": _ranked_companies(by_card)}

    yield {
        "type": "done",
        "search_errors": search_errors,
        "already_in_list_count": len(listed_hits),
        "excluded_location_count": excluded_location_count,
    }
