"""Respectful walking-route lookups for attractions with verified OSM coordinates."""
from functools import lru_cache
import logging
from math import ceil
from threading import Lock
from time import monotonic, sleep

import requests


ROUTING_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/driving"
ROUTING_SOURCE = "OpenStreetMap / OSRM · הליכה"
HEADERS = {"User-Agent": "TravelDNA-course-project/1.0 (+https://traveldna-production.up.railway.app/)"}
_request_lock = Lock()
_last_request_at = 0.0


def _wait_for_slot():
    """Keep within the public server's one-request-per-second policy."""
    global _last_request_at
    with _request_lock:
        remaining = 1 - (monotonic() - _last_request_at)
        if remaining > 0:
            sleep(remaining)
        _last_request_at = monotonic()


@lru_cache(maxsize=1024)
def walking_minutes(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> int | None:
    """Return a route duration, never pretending an unavailable route was measured."""
    _wait_for_slot()
    coordinates = f"{from_lon:.6f},{from_lat:.6f};{to_lon:.6f},{to_lat:.6f}"
    try:
        response = requests.get(
            f"{ROUTING_URL}/{coordinates}", params={"overview": "false"},
            headers=HEADERS, timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        duration = payload.get("routes", [{}])[0].get("duration") if payload.get("code") == "Ok" else None
        return ceil(float(duration) / 60) if duration is not None else None
    except (requests.RequestException, ValueError, TypeError, IndexError, KeyError):
        logging.getLogger(__name__).info("Walking route lookup unavailable")
        return None


def enrich_trip_travel_times(trip) -> None:
    """Attach walking times only where both adjacent attractions have OSM locations."""
    found_route = False
    for day in trip.days:
        attractions = [activity for activity in sorted(day.activities, key=lambda a: a.start)
                       if activity.kind == "attraction"]
        for previous, activity in zip(attractions, attractions[1:]):
            if not all(value is not None for value in (
                previous.latitude, previous.longitude, activity.latitude, activity.longitude,
            )):
                continue
            duration = walking_minutes(
                previous.latitude, previous.longitude, activity.latitude, activity.longitude,
            )
            if duration is not None:
                activity.travel_minutes = duration
                activity.travel_source = ROUTING_SOURCE
                found_route = True
    if found_route:
        trip.sources = list(dict.fromkeys([*trip.sources, "https://routing.openstreetmap.de/"]))
