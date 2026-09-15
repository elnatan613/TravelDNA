from datetime import date
from unittest.mock import Mock, patch

from app.routing import enrich_trip_travel_times, walking_minutes
from app.trip_models import Activity, Itinerary, TripDay


def _trip():
    return Itinerary(summary="מסלול", sources=[], days=[TripDay(date=date.today(), activities=[
        Activity(name="ראשון", description="", start="09:00", end="10:00", latitude=48.85, longitude=2.35),
        Activity(name="ארוחה", description="", start="10:00", end="11:00", kind="meal"),
        Activity(name="שני", description="", start="11:30", end="12:30", latitude=48.86, longitude=2.36),
    ])])


def test_routing_adds_walking_time_and_attribution():
    walking_minutes.cache_clear()
    response = Mock()
    response.json.return_value = {"code": "Ok", "routes": [{"duration": 661}]}
    with patch("app.routing.requests.get", return_value=response) as get:
        trip = _trip()
        enrich_trip_travel_times(trip)

    second = trip.days[0].activities[2]
    assert second.travel_minutes == 12
    assert "הליכה" in second.travel_source
    assert "https://routing.openstreetmap.de/" in trip.sources
    assert get.call_count == 1


def test_failed_routing_does_not_invent_a_duration():
    walking_minutes.cache_clear()
    response = Mock()
    response.json.return_value = {"code": "NoRoute", "routes": []}
    with patch("app.routing.requests.get", return_value=response):
        trip = _trip()
        enrich_trip_travel_times(trip)

    assert trip.days[0].activities[2].travel_minutes is None
