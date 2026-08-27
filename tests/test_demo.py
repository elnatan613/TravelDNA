"""בדיקת אינטגרציה קלה לזרימה המלאה בדמו, בלי קריאות רשת או Gemini."""

import os
from unittest import mock

from streamlit.testing.v1 import AppTest


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEMO_PATH = os.path.join(_PROJECT_ROOT, "app", "demo.py")


def test_demo_recommendation_to_itinerary_flow():
    fake_agent = mock.Mock()
    fake_agent.plan_trip.return_value = "## Day 1\nTest itinerary"

    with mock.patch("agent.trip_planner.TripPlanningAgent", return_value=fake_agent):
        app = AppTest.from_file(_DEMO_PATH).run(timeout=20)
        assert not app.exception

        app.button[0].click().run(timeout=20)
        assert not app.exception
        assert app.selectbox[0].label == "יעד"
        assert len(app.selectbox[0].options) == 5
        selected_city = app.selectbox[0].value

        app.button[1].click().run(timeout=20)

    assert not app.exception
    fake_agent.plan_trip.assert_called_once()
    call = fake_agent.plan_trip.call_args
    assert call.args == (selected_city,)
    assert call.kwargs["days"] == 3
    assert call.kwargs["budget_total_usd"] == 500.0
    assert "TravelDNA preference scores" in call.kwargs["preferences"]
    assert any("Test itinerary" in element.value for element in app.markdown)
