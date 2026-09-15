from unittest.mock import Mock, patch

from app.location_lookup import find_venue


def test_venue_lookup_returns_a_verified_address_and_map():
    response = Mock()
    response.json.return_value = [{
        "lat": "48.860611", "lon": "2.337644",
        "address": {"road": "Rue de Rivoli", "house_number": "99", "city": "Paris"},
        "type": "museum", "extratags": {"opening_hours": "Tu-Su 09:00-18:00", "website": "https://example.com"},
    }]
    find_venue.cache_clear()
    with patch("app.location_lookup.requests.get", return_value=response) as get:
        result = find_venue("מוזיאון הלובר", "Paris")
    assert result["address"] == "Rue de Rivoli 99, Paris"
    assert result["location_source"] == "OpenStreetMap"
    assert "openstreetmap.org" in result["map_url"]
    assert result["venue_type"] == "מוזיאון"
    assert result["opening_hours"] == "Tu-Su 09:00-18:00"
    assert result["estimated_cost"] == "כ־12–25 אירו לאדם"
    assert result["website"] == "https://example.com"
    assert get.call_args.kwargs["params"]["q"] == "מוזיאון הלובר, Paris"


def test_venue_lookup_does_not_create_an_address_when_no_result():
    response = Mock()
    response.json.return_value = []
    find_venue.cache_clear()
    with patch("app.location_lookup.requests.get", return_value=response):
        assert find_venue("מקום כללי", "Paris") is None
