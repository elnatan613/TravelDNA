"""Best-effort venue lookup using the project's existing OpenStreetMap source."""
from functools import lru_cache
import logging
from time import sleep

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "TravelDNA-course-project/1.0 (venue lookup)"}


def _address(tags: dict) -> str | None:
    """Make a concise address from an OpenStreetMap/Nominatim result."""
    street = " ".join(part for part in (tags.get("road"), tags.get("house_number")) if part)
    locality = tags.get("suburb") or tags.get("neighbourhood") or tags.get("city") or tags.get("town")
    parts = [part for part in (street, locality, tags.get("city") if locality != tags.get("city") else None) if part]
    return ", ".join(dict.fromkeys(parts)) or None


@lru_cache(maxsize=512)
def find_venue(name: str, city: str) -> dict | None:
    """Return verified OSM evidence, or None when a place cannot be identified."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": f"{name}, {city}", "format": "jsonv2", "limit": 1,
                    "addressdetails": 1, "accept-language": "he"},
            headers=HEADERS,
            timeout=8,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        item = rows[0]
        latitude, longitude = float(item["lat"]), float(item["lon"])
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return None
        address = _address(item.get("address", {}))
        if not address:
            return None
        return {
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "map_url": f"https://www.openstreetmap.org/?mlat={latitude:.6f}&mlon={longitude:.6f}#map=17/{latitude:.6f}/{longitude:.6f}",
            "location_source": "OpenStreetMap",
        }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logging.getLogger(__name__).info("OpenStreetMap venue lookup unavailable for %s", name)
        return None


def enrich_trip_locations(trip, city: str) -> None:
    """Attach OSM evidence to attractions without inventing a location."""
    seen, looked_up = set(), False
    for day in trip.days:
        for activity in day.activities:
            if activity.kind != "attraction" or activity.name in seen:
                continue
            seen.add(activity.name)
            # Nominatim is a shared public service. The planner's single lock
            # keeps requests serial, and this keeps distinct requests to 1/s.
            if looked_up:
                sleep(1)
            looked_up = True
            location = find_venue(activity.name, city)
            if location:
                for key, value in location.items():
                    setattr(activity, key, value)
