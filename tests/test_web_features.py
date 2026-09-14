"""Offline checks for route feasibility, forecast boundaries and API behavior."""
from datetime import date, timedelta
from unittest.mock import Mock, patch
import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.feasibility import validate_itinerary
from app.trip_models import Activity, Itinerary, TripDay
from app.weather import packing_for_trip


def activity(**kw):
    return Activity(**dict(name="מוזיאון", description="ביקור", start="09:00", end="11:00", **kw))


def trip(activities):
    return Itinerary(summary="מסלול", days=[TripDay(date=date.today(), activities=activities)], sources=[])


def test_unknown_data_cannot_pass_validation():
    report = validate_itinerary(trip([activity()]))
    assert report["status"] == "partial"
    assert report["unknown"]
    assert report["coverage_percent"] < 100


def test_overlap_and_heavy_day():
    report = validate_itinerary(trip([activity(heavy=True) for _ in range(4)]))
    assert any("חופפת" in s for s in report["issues"])
    assert any("עמוס" in s for s in report["issues"])


def test_closure_requires_dated_evidence():
    report = validate_itinerary(trip([activity(closed=True, opening_source="source", opening_date=date.today())]))
    assert report["status"] == "issues"
    report = validate_itinerary(trip([activity(closed=True, opening_source="source", opening_date=date.today()-timedelta(days=1))]))
    assert report["status"] == "partial"


def test_travel_and_geographic_impossibility():
    first = activity(latitude=48.8, longitude=2.3, location_source="source")
    second = Activity(name="אתר", description="ביקור", start="11:10", end="12:00", travel_minutes=60, travel_source="route")
    assert any("נדרשות 60" in s for s in validate_itinerary(trip([first, second]))["issues"])
    second.travel_source = None
    second.latitude, second.longitude, second.location_source = 51.5, -0.1, "source"
    assert any("מרחק אווירי" in s for s in validate_itinerary(trip([first, second]))["issues"])


def test_invalid_time_rejected():
    with pytest.raises(ValueError):
        Activity(name="אתר", description="", start="25:00", end="26:00")


def test_travel_blocks_are_not_attractions_and_count_as_transfer_time():
    first = activity()
    transit = Activity(name="מעבר", description="", start="11:00", end="12:00", kind="travel")
    second = Activity(name="אתר", description="", start="12:00", end="13:00", travel_minutes=60, travel_source="route")
    report = validate_itinerary(trip([first, transit, second]))
    assert not report["issues"]
    assert not any("מעבר: שעות" in s for s in report["unknown"])


def test_meals_do_not_need_opening_hours_or_make_a_day_overloaded():
    meal = Activity(name="ארוחת צהריים", description="בחירה גמישה", start="09:00", end="22:00", kind="meal")
    report = validate_itinerary(trip([meal]))

    assert not report["issues"]
    assert not any("ארוחת צהריים: שעות" in item for item in report["unknown"])


def test_outside_forecast_never_calls_weather():
    with patch("app.weather.requests.get") as get:
        report = packing_for_trip({}, date.today()+timedelta(days=14), 3)
    get.assert_not_called()
    assert report["status"] == "unavailable"


def test_rain_and_cold_packing():
    response = Mock()
    response.json.return_value = {"daily": {"time": [date.today().isoformat()], "temperature_2m_min": [3],
        "temperature_2m_max": [12], "precipitation_probability_max": [80]}}
    with patch("app.weather.requests.get", return_value=response):
        report = packing_for_trip({"lat": 48, "lng": 2}, date.today(), 1)
    assert report["status"] == "forecast"
    assert "מעיל חם" in report["items"]
    assert "מעיל גשם או מטרייה" in report["items"]


def test_partial_forecast_is_not_presented_as_complete():
    response = Mock()
    response.json.return_value = {"daily": {"time": [date.today().isoformat()], "temperature_2m_min": [None],
        "temperature_2m_max": [12], "precipitation_probability_max": [80]}}
    with patch("app.weather.requests.get", return_value=response):
        assert packing_for_trip({"lat": 48, "lng": 2}, date.today(), 1)["status"] == "unavailable"


client = TestClient(app)


def test_cities_and_input_validation():
    assert len(client.get("/api/cities").json()) == 18
    assert client.post("/api/plan", json={"city":"Paris", "start_date":date.today().isoformat(), "days":0}).status_code == 422
    assert client.post("/api/plan", json={"city":"Atlantis", "start_date":date.today().isoformat()}).status_code == 422
    assert client.post("/api/match", json={"answers": {}, "importance": {}}).status_code == 422


def test_plan_api_uses_validation_and_returns_exportable_structure():
    with patch("agent.structured_trip.build_structured_trip", return_value=(trip([activity()]), None)), \
         patch("app.api.get_agent"), patch("app.api.packing_for_trip", return_value={"items": []}):
        response = client.post("/api/plan", json={"city":"Paris", "start_date":date.today().isoformat()})
    assert response.status_code == 200
    assert response.json()["validation"]["status"] == "partial"
    assert response.json()["guide_review"] is None


def test_planner_errors_do_not_expose_secrets_and_release_lock():
    from app.api import planning_lock
    with patch("app.api.get_agent", side_effect=RuntimeError("secret-token")):
        response = client.post("/api/plan", json={"city":"Paris", "start_date":date.today().isoformat()})
    assert response.status_code == 503
    assert "secret-token" not in response.text
    assert not planning_lock.locked()


def test_structuring_strips_invented_evidence_and_sources():
    from agent.structured_trip import build_structured_trip
    from app.trip_models import TripRequest
    generated = trip([activity(latitude=48, longitude=2, location_source="invented", closed=True,
                              opening_source="invented", opening_date=date.today())])
    generated.sources = ["https://example.com/source", "https://invented.com"]
    agent = Mock()
    agent.plan_trip.return_value = "מסלול\nhttps://example.com/source"
    agent.client.models.generate_content.side_effect = [Mock(text=generated.model_dump_json()),
                                                      Mock(text='{"score":70,"notes":["קחו הפסקה"]}')]
    with patch("app.location_lookup.enrich_trip_locations") as enrich:
        result, review = build_structured_trip(agent, TripRequest(city="Paris", start_date=date.today(), days=1))
    assert result.sources == ["https://example.com/source"]
    assert result.days[0].activities[0].latitude is None
    assert result.days[0].activities[0].closed is None
    enrich.assert_called_once_with(result, "Paris")
    assert review["score"] == 70


def test_structuring_rejects_wrong_dates():
    from agent.structured_trip import build_structured_trip
    from app.trip_models import TripRequest
    agent = Mock()
    agent.client.models.generate_content.return_value.text = trip([activity()]).model_dump_json()
    with pytest.raises(ValueError, match="incorrect dates"):
        build_structured_trip(agent, TripRequest(city="Paris", start_date=date.today()+timedelta(days=1), days=1))


def test_structuring_returns_basic_trip_when_provider_is_unavailable():
    from agent.structured_trip import build_structured_trip
    from agent.trip_planner import TripServiceUnavailable
    from app.trip_models import TripRequest
    agent = Mock()
    agent.plan_trip.side_effect = TripServiceUnavailable("unavailable")

    result, review = build_structured_trip(agent, TripRequest(city="Paris", start_date=date.today(), days=2))

    assert len(result.days) == 2
    assert result.sources == ["https://en.wikivoyage.org/wiki/Paris"]
    assert review is None
