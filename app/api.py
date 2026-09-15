"""Local React API. Run: python -m uvicorn app.api:app --host 127.0.0.1."""
from functools import lru_cache
from pathlib import Path
from threading import Lock
from collections import defaultdict, deque
from time import monotonic
import logging
import math

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from app.city_backgrounds import CITY_BACKGROUNDS
from app.trip_models import TripRequest
from app.feasibility import validate_itinerary
from app.weather import packing_for_trip
from app.survey import Survey, matching_profile, interpret_notes, survey_pace
from config import AXES
from matching.matcher import load_destinations, rank_destinations

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="TravelDNA")
planning_lock = Lock()
rate_limit_lock = Lock()
rate_limit_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
CITY_LABELS = dict(zip(
    ["Paris", "Barcelona", "Amsterdam", "Prague", "Vienna", "Reykjavik", "Lisbon", "Budapest", "Krakow", "Berlin", "Rome", "Florence", "Copenhagen", "Stockholm", "Dublin", "Edinburgh", "Athens", "Porto"],
    ["פריז", "ברצלונה", "אמסטרדם", "פראג", "וינה", "רייקיאוויק", "ליסבון", "בודפשט", "קרקוב", "ברלין", "רומא", "פירנצה", "קופנהגן", "סטוקהולם", "דבלין", "אדינבורו", "אתונה", "פורטו"]))


def destinations():
    return load_destinations(str(ROOT / "data/processed/destinations.json"))


def enforce_rate_limit(request: Request, action: str, limit: int, window_seconds: int):
    """Bound public, billable AI requests per visitor in this single service."""
    client = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    client = client.split(",", maxsplit=1)[0].strip()
    now = monotonic()
    key = (client, action)
    with rate_limit_lock:
        events = rate_limit_events[key]
        while events and events[0] <= now - window_seconds:
            events.popleft()
        if len(events) >= limit:
            raise HTTPException(429, "הגעתם למגבלת הבקשות הזמנית. נסו שוב מאוחר יותר.")
        events.append(now)


@lru_cache(maxsize=1)
def get_agent():
    from agent.trip_planner import TripPlanningAgent
    return TripPlanningAgent()


class MatchRequest(BaseModel):
    answers: dict[str, int]
    importance: dict[str, int]
    text: str = Field(default="", max_length=4000)
    kosher: bool = False

    @model_validator(mode="after")
    def check_axes(self):
        for values in (self.answers, self.importance):
            if set(values) != set(AXES) or any(v < 1 or v > 5 for v in values.values()):
                raise ValueError("כל העדפה וחשיבות חייבות להיות בין 1 ל־5")
        return self


@app.get("/api/cities")
def cities():
    return [{"city": d["city"], "label": CITY_LABELS.get(d["city"], d["city"]),
             "background": CITY_BACKGROUNDS.get(d["city"], "")} for d in destinations()]


@app.get("/health")
def health():
    """A lightweight endpoint for the hosting platform health check."""
    return {"status": "ok"}


@app.post("/api/match")
def match(request: MatchRequest):
    from nlp.profile_extractor import build_travel_profile, extract_importance_weights
    try:
        profile = build_travel_profile(request.answers, request.text)
        weights = extract_importance_weights(request.importance)
        ranked = rank_destinations(profile, weights, destinations(), requires_kosher=request.kosher)
        maximum = math.sqrt(sum(weights.values()))
        return {"results": [{"city": d["city"], "label": CITY_LABELS.get(d["city"], d["city"]),
                 "match_percent": round(100 * max(0, 1 - d["distance"] / maximum))} for d in ranked[:5]]}
    except Exception:
        logging.exception("Destination matching failed")
        raise HTTPException(503, "לא ניתן לחשב התאמה כרגע. אפשר לנסות שוב או לבחור יעד ישירות.")


@app.post("/api/plan")
def plan(request: TripRequest, http_request: Request):
    destination = next((d for d in destinations() if d["city"] == request.city), None)
    if destination is None:
        raise HTTPException(422, "היעד אינו נתמך")
    # The public providers used while building a trip have strict request
    # limits. Queue requests in this process instead of turning another
    # visitor's active build into an error for the current visitor.
    if not planning_lock.acquire(timeout=180):
        raise HTTPException(503, "התכנון מתעכב מהרגיל. נסו שוב בעוד רגע.")
    try:
        enforce_rate_limit(http_request, "plan", limit=3, window_seconds=600)
        from agent.structured_trip import build_structured_trip
        trip, review = build_structured_trip(get_agent(), request)
        return {"request": request.model_dump(mode="json"), "itinerary": trip.model_dump(mode="json"),
                "validation": validate_itinerary(trip, request.pace), "guide_review": review,
                "packing": packing_for_trip(destination, request.start_date, request.days)}
    except Exception:
        logging.exception("Trip planning failed")
        raise HTTPException(503, "לא ניתן לבנות מסלול כרגע. בדקו את הגדרת השירות ונסו שוב.")
    finally:
        planning_lock.release()


@app.post("/api/discover")
def discover(survey: Survey, http_request: Request):
    enforce_rate_limit(http_request, "discover", limit=10, window_seconds=600)
    profile, weights = matching_profile(survey)
    try:
        notes = interpret_notes(survey.notes)
    except Exception:
        logging.exception("Survey notes interpretation failed")
        raise HTTPException(503, "לא הצלחנו לעבד את ההערות כרגע. הן נשמרו; נסו שוב או בחרו יעד ישירות.")
    for override in notes.overrides:
        profile[override.axis] = override.value
        weights[override.axis] = 1.0
    ranked = rank_destinations(profile, weights, destinations(), requires_kosher=notes.requires_kosher)
    maximum = math.sqrt(sum(weights.values()))
    pace = survey_pace(survey)
    for override in notes.overrides:
        if override.axis == "activity_density":
            pace = "relaxed" if override.value < 0.4 else "busy" if override.value > 0.7 else "balanced"
    return {"pace": pace, "has_signal": maximum > 0, "results": [
        {"city": d["city"], "label": CITY_LABELS.get(d["city"], d["city"]),
         "match_percent": round(100 * max(0, 1-d["distance"]/maximum)) if maximum else None}
        for d in ranked[:3]]}


dist = ROOT / "frontend/dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
