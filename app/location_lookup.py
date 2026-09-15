"""Best-effort venue lookup using the project's existing OpenStreetMap source."""
from functools import lru_cache
import logging
from threading import Lock
from time import monotonic, sleep

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "TravelDNA-course-project/1.0 (venue lookup)"}
_nominatim_lock = Lock()
_last_nominatim_request = 0.0

_TYPE_LABELS = {
    "museum": "מוזיאון", "gallery": "גלריה", "attraction": "אטרקציה",
    "viewpoint": "נקודת תצפית", "marketplace": "שוק", "market": "שוק",
    "monument": "אנדרטה", "memorial": "אתר זיכרון", "castle": "טירה",
    "park": "פארק", "zoo": "גן חיות", "theme_park": "פארק שעשועים",
    "restaurant": "מסעדה", "cafe": "בית קפה", "fast_food": "אוכל מהיר",
}

_CURRENCY = {
    "Paris": "אירו", "Barcelona": "אירו", "Amsterdam": "אירו", "Vienna": "אירו",
    "Lisbon": "אירו", "Berlin": "אירו", "Rome": "אירו", "Florence": "אירו",
    "Dublin": "אירו", "Athens": "אירו", "Porto": "אירו", "Prague": "קורונה צ׳כית",
    "Budapest": "פורינט", "Krakow": "זלוטי", "Reykjavik": "קרונה איסלנדית",
    "Copenhagen": "קרונה דנית", "Stockholm": "קרונה שוודית", "Edinburgh": "ליש״ט",
}

_CANDIDATE_CATEGORIES = ("museum", "gallery", "market", "park", "restaurant", "cafe")


def _nominatim_search(params: dict) -> list[dict]:
    """Use Nominatim respectfully: one serialized request per second."""
    global _last_nominatim_request
    with _nominatim_lock:
        wait = 1 - (monotonic() - _last_nominatim_request)
        if wait > 0:
            sleep(wait)
        try:
            response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=8)
            response.raise_for_status()
            rows = response.json()
            return rows if isinstance(rows, list) else []
        finally:
            _last_nominatim_request = monotonic()


def _venue_type(item: dict) -> str | None:
    return _TYPE_LABELS.get(item.get("type")) or _TYPE_LABELS.get(item.get("category"))


def _estimated_cost(item: dict, city: str) -> str | None:
    """Give a transparent category-level estimate, never a claimed venue price."""
    venue_type = item.get("type")
    if venue_type in {"marketplace", "market", "viewpoint", "memorial", "monument", "park"}:
        return "לרוב חינם; קניות או תוספות לפי בחירה"
    currency = _CURRENCY.get(city, "מטבע מקומי")
    ranges = {
        "museum": "12–25", "gallery": "8–20", "attraction": "10–25", "castle": "12–25",
        "zoo": "20–40", "theme_park": "30–60", "restaurant": "15–35", "cafe": "5–15",
    }
    if venue_type in ranges:
        return f"כ־{ranges[venue_type]} {currency} לאדם"
    return None


def _address(tags: dict) -> str | None:
    """Make a concise address from an OpenStreetMap/Nominatim result."""
    tags = tags or {}
    street = " ".join(part for part in (tags.get("road"), tags.get("house_number")) if part)
    locality = tags.get("suburb") or tags.get("neighbourhood") or tags.get("city") or tags.get("town")
    parts = [part for part in (street, locality, tags.get("city") if locality != tags.get("city") else None) if part]
    return ", ".join(dict.fromkeys(parts)) or None


@lru_cache(maxsize=512)
def find_venue(name: str, city: str) -> dict | None:
    """Return verified OSM evidence, or None when a place cannot be identified."""
    try:
        rows = _nominatim_search({"q": f"{name}, {city}", "format": "jsonv2", "limit": 1,
                                  "addressdetails": 1, "extratags": 1, "namedetails": 1,
                                  "accept-language": "he"})
        if not rows:
            return None
        item = rows[0]
        latitude, longitude = float(item["lat"]), float(item["lon"])
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return None
        address = _address(item.get("address"))
        if not address:
            return None
        # Nominatim may explicitly return null for optional extra tags.
        # An absent website or opening-hours field must not cancel the route.
        extra = item.get("extratags") or {}
        website = extra.get("website") or extra.get("contact:website")
        if website and not website.startswith(("https://", "http://")):
            website = None
        return {
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "map_url": f"https://www.openstreetmap.org/?mlat={latitude:.6f}&mlon={longitude:.6f}#map=17/{latitude:.6f}/{longitude:.6f}",
            "location_source": "OpenStreetMap",
            "venue_type": _venue_type(item),
            "opening_hours": extra.get("opening_hours"),
            "website": website,
            "estimated_cost": _estimated_cost(item, city),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        logging.getLogger(__name__).info("OpenStreetMap venue lookup unavailable for %s", name)
        return None


def _candidate_name(item: dict) -> str | None:
    names = item.get("namedetails") or {}
    name = names.get("name") or names.get("name:en") or item.get("name")
    if not name:
        name = (item.get("display_name") or "").split(",", maxsplit=1)[0]
    return name.strip() if isinstance(name, str) and name.strip() else None


@lru_cache(maxsize=64)
def venue_candidates(city: str, per_category: int = 3) -> tuple[dict, ...]:
    """Find a bounded, diverse set of named places before an itinerary is written.

    These are candidate names, not opening-hours or price claims. Full details
    are still looked up only for the places selected in the final itinerary.
    """
    candidates, seen = [], set()
    for category in _CANDIDATE_CATEGORIES:
        try:
            rows = _nominatim_search({"q": f"{category}, {city}", "format": "jsonv2",
                                      "limit": per_category, "addressdetails": 1,
                                      "namedetails": 1, "accept-language": "en"})
        except requests.RequestException:
            logging.getLogger(__name__).info("OpenStreetMap candidate lookup unavailable for %s", city)
            continue
        for item in rows:
            name = _candidate_name(item)
            if not name:
                continue
            key = "".join(name.casefold().split())
            if key in seen:
                continue
            seen.add(key)
            address = _address(item.get("address", {}))
            candidates.append({"name": name, "category": category, "area": address})
    return tuple(candidates)


def candidate_pool_for_planning(city: str, days: int) -> str:
    """Format enough live, named candidates for a multi-day planning prompt."""
    per_category = min(5, max(2, (days + 1) // 2))
    candidates = venue_candidates(city, per_category)
    if not candidates:
        return "No live venue candidates were available; use only named venues from the curated guide."
    lines = []
    for candidate in candidates:
        area = f" — {candidate['area']}" if candidate["area"] else ""
        lines.append(f"- {candidate['category']}: {candidate['name']}{area}")
    return "\n".join(lines)


def enrich_trip_locations(trip, city: str) -> None:
    """Attach OSM evidence to named attractions and meal venues only."""
    seen, looked_up = set(), False
    for day in trip.days:
        for activity in day.activities:
            if activity.kind not in {"attraction", "meal"} or activity.name in seen:
                continue
            seen.add(activity.name)
            # _nominatim_search serializes all calls, including the candidate
            # pool requested before this enrichment step.
            location = find_venue(activity.name, city)
            if location:
                for key, value in location.items():
                    setattr(activity, key, value)
