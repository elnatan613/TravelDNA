from datetime import date
from unittest.mock import Mock, patch
import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.survey import Survey, CARD_IDS, matching_profile, planner_preferences, survey_pace, NotesInterpretation
from app.trip_models import TripRequest, Itinerary, TripDay, Activity


def survey(**choices):
    return Survey(party="couple", choices={key:choices.get(key,"skip") for key in CARD_IDS})


def test_skips_have_no_matching_weight_or_budget_inference():
    profile, weights = matching_profile(survey())
    assert all(v == 0 for v in weights.values())
    assert all(v == .5 for v in profile.values())
    _, weights = matching_profile(survey(**{key:"yes" for key in CARD_IDS}))
    assert weights["price_sensitivity"] == 0


def test_city_and_nature_do_not_erase_each_other_in_planner():
    value = survey(city="yes", picnic="yes", hike="no")
    text = planner_preferences(value)
    assert "גם בעיר וגם בטבע" in text
    assert "ללא מסלולי הליכה ארוכים" in text
    assert .4 < matching_profile(value)[0]["urban"] < .6


def test_dislike_is_weaker_than_explicit_interest():
    positive = matching_profile(survey(museum="yes"))
    negative = matching_profile(survey(museum="no"))
    assert negative[1]["culture"] < positive[1]["culture"]
    assert negative[0]["culture"] > 0


def test_mixed_pace_and_music_without_party():
    value=survey(**{"free-time":"yes", "full-day":"yes", "music":"yes", "nightlife":"no"})
    assert survey_pace(value) == "balanced"
    assert "זו אינה סתירה" in planner_preferences(value)
    assert "אין לתכנן מסיבה" in planner_preferences(value)


def test_complete_deck_and_family_validation():
    with pytest.raises(ValueError):
        Survey(party="couple",choices={})
    with pytest.raises(ValueError):
        Survey(party="friends",children=True,child_ages=[4],choices=survey().choices)
    with pytest.raises(ValueError):
        Survey(party="family",children=True,child_ages=[18],choices=survey().choices)
    family=Survey(party="family",children=True,child_ages=[0,8],choices=survey().choices)
    assert "0, 8" in planner_preferences(family)


def test_notes_preserved_with_precedence():
    value=survey(hike="yes")
    value.notes="ללא עליות, חשובה לנו כשרות"
    assert planner_preferences(value).endswith(value.notes)
    assert "גוברות" in planner_preferences(value)


client=TestClient(app)


def test_blank_notes_do_not_call_model_and_uninformed_matches_have_no_percent():
    response=client.post("/api/discover",json=survey().model_dump())
    assert response.status_code == 200
    assert response.json()["has_signal"] is False
    assert all(r["match_percent"] is None for r in response.json()["results"])


def test_explicit_notes_override_pace_and_kosher_filters():
    note_result=NotesInterpretation(overrides=[{"axis":"activity_density","value":.1}],requires_kosher=True)
    with patch("app.api.interpret_notes",return_value=note_result):
        response=client.post("/api/discover",json=survey(**{"full-day":"yes"}).model_dump())
    assert response.status_code == 200
    assert response.json()["pace"] == "relaxed"
    from app.api import destinations
    eligible={d["city"] for d in destinations() if d.get("kosher_availability",0)>=.3}
    assert all(r["city"] in eligible for r in response.json()["results"])


def test_notes_provider_failure_does_not_silently_ignore_constraints():
    with patch("app.api.interpret_notes",side_effect=RuntimeError("internal")):
        response=client.post("/api/discover",json=survey().model_dump())
    assert response.status_code==503
    assert "internal" not in response.text


def test_planner_receives_raw_choices_and_notes():
    from agent.structured_trip import build_structured_trip
    value=survey(beach="yes",hike="no")
    value.notes="טיול עם מעט הליכה"
    request=TripRequest(city="Paris",start_date=date.today(),days=1,survey=value)
    result=Itinerary(summary="טיול",days=[TripDay(date=date.today(),activities=[Activity(name="ביקור",description="טיול",start="09:00",end="10:00")])],sources=[])
    agent=Mock()
    agent.plan_trip.return_value="טיול"
    agent.client.models.generate_content.side_effect=[Mock(text=result.model_dump_json()),Mock(text='{"score":80,"notes":[]}')]
    build_structured_trip(agent,request)
    sent=agent.plan_trip.call_args.args[3]
    assert "חצי יום בחוף" in sent
    assert "שלוש שעות" in sent
    assert value.notes in sent
