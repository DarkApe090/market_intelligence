from app.scrappers.common import USER_AGENT, _fold, get_cached_json


NOMINATIM = "https://nominatim.openstreetmap.org/search"
PLACE_TYPES = {
    "country", "city", "town", "village", "hamlet", "municipality",
    "state", "county", "province", "administrative",
}


def search_places(query: str, limit: int = 8) -> list[dict]:
    text = query.strip()
    if len(text) < 2:
        return []
    payload = get_cached_json(
        NOMINATIM,
        {"q": text, "format": "json", "addressdetails": 1, "limit": str(limit)},
        {"Accept-Language": "pt", "User-Agent": USER_AGENT},
    )
    if not isinstance(payload, list):
        return []
    seen: set[str] = set()
    places = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("addresstype") or item.get("type") or "")
        if kind not in PLACE_TYPES:
            continue
        place = _from_nominatim(item, kind)
        needle = _fold(text)
        if not place or place["label"] in seen:
            continue
        if needle not in _fold(place["name"]) and needle not in _fold(place["country"]):
            continue
        seen.add(place["label"])
        places.append(place)
        if len(places) >= limit:
            break
    return places


def _from_nominatim(item: dict, kind: str) -> dict | None:
    address = item.get("address") if isinstance(item.get("address"), dict) else {}
    country = str(address.get("country") or "").strip()
    is_country = kind == "country"
    name = country if is_country else str(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or item.get("name")
        or ""
    ).strip()
    if not name:
        return None
    label = name if is_country or not country or name.casefold() == country.casefold() else f"{name}, {country}"
    return {
        "label": label,
        "name": name,
        "country": country or name,
        "kind": "country" if is_country else "city",
    }
