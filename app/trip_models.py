"""Shared API and generated-itinerary contracts."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from app.survey import Survey


class Activity(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    heavy: bool = False
    kind: Literal["attraction", "meal", "travel", "break"] = "attraction"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_source: str | None = None
    opening_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    opening_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closed: bool | None = None
    opening_source: str | None = None
    opening_date: date | None = None
    travel_minutes: int | None = Field(default=None, ge=0, le=1440)
    travel_source: str | None = None


class TripDay(BaseModel):
    date: date
    activities: list[Activity] = Field(min_length=1, max_length=20)


class Itinerary(BaseModel):
    summary: str
    days: list[TripDay] = Field(min_length=1, max_length=14)
    sources: list[str]


class GuideReview(BaseModel):
    score: int = Field(ge=0, le=100)
    notes: list[str] = Field(max_length=10)


class TripRequest(BaseModel):
    city: str
    start_date: date
    days: int = Field(default=3, ge=1, le=14)
    budget: float = Field(default=500, gt=0, le=1000000, allow_inf_nan=False)
    preferences: str = Field(default="", max_length=4000)
    pace: Literal["relaxed", "balanced", "busy"] = "balanced"
    survey: Survey | None = None

    @model_validator(mode="after")
    def future_trip(self):
        if self.start_date < date.today():
            raise ValueError("תאריך היציאה חייב להיות היום או בעתיד")
        return self
