"""
בדיקות יחידה ל-scripts/kashrut_fetcher.py.

לא פוגעות ברשת (Overpass) - מדמות (mock) את fetch_raw_kosher_counts ובודקות
רק את לוגיקת השקלול/נרמול וטיפול בכשלים.
"""

import os
import sys
from unittest import mock

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)
sys.path.append(os.path.join(_PROJECT_ROOT, "scripts"))

import kashrut_fetcher as kf


def _coords_by_city(city_names):
    return {c: {"name": c, "lat": 0.0, "lng": 0.0} for c in city_names}


def test_more_synagogues_and_kosher_food_scores_higher():
    raw = {
        "Vienna": {"synagogue": 8, "kosher_food": 22},
        "Berlin": {"synagogue": 5, "kosher_food": 19},
        "Reykjavik": {"synagogue": 0, "kosher_food": 0},
    }

    def fake_fetch(coords, radius=None, max_retries=3):
        return raw[coords["name"]], True

    with mock.patch("kashrut_fetcher.fetch_raw_kosher_counts", side_effect=fake_fetch):
        scores = kf.compute_jewish_community_scores(_coords_by_city(raw))

    assert scores["Vienna"] == 1.0
    assert scores["Reykjavik"] == 0.0
    assert scores["Reykjavik"] < scores["Berlin"] < scores["Vienna"]


def test_all_scores_in_unit_range():
    raw = {
        "A": {"synagogue": 3, "kosher_food": 10},
        "B": {"synagogue": 1, "kosher_food": 1},
        "C": {"synagogue": 0, "kosher_food": 5},
    }

    def fake_fetch(coords, radius=None, max_retries=3):
        return raw[coords["name"]], True

    with mock.patch("kashrut_fetcher.fetch_raw_kosher_counts", side_effect=fake_fetch):
        scores = kf.compute_jewish_community_scores(_coords_by_city(raw))

    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_persistent_failure_gets_neutral_score_not_fake_zero():
    # עיר שנכשלת בכל הניסיונות (גם בסיבוב החזרה) צריכה לקבל 0.5 ניטרלי,
    # לא 0.0 - כדי לא "לזייף" מסקנה של "אין קהילה יהודית" מכשל רשת. שתי
    # ערים תקינות (לא רק אחת) כדי שיהיה בסיס השוואה אמיתי לנרמול.
    raw = {
        "Vienna": {"synagogue": 8, "kosher_food": 22},
        "Reykjavik": {"synagogue": 0, "kosher_food": 0},
    }

    def fake_fetch(coords, radius=None, max_retries=3):
        if coords["name"] == "BrokenCity":
            return {"synagogue": 0, "kosher_food": 0}, False
        return raw[coords["name"]], True

    with mock.patch("kashrut_fetcher.fetch_raw_kosher_counts", side_effect=fake_fetch), \
         mock.patch("kashrut_fetcher.time.sleep"):
        scores = kf.compute_jewish_community_scores(_coords_by_city(["Vienna", "Reykjavik", "BrokenCity"]))

    assert scores["BrokenCity"] == 0.5
    assert scores["Vienna"] == 1.0
    assert scores["Reykjavik"] == 0.0


def test_empty_input_returns_empty_dict():
    assert kf.compute_jewish_community_scores({}) == {}


def test_normalize_min_max_matches_destination_scraper_behavior():
    # אותה לוגיקה כמו destination_scraper.normalize_min_max - נבדקת כאן
    # בנפרד כי קיימת עותק מקומי (בכוונה, ראו הערה בראש קובץ kashrut_fetcher.py)
    assert kf.normalize_min_max({"A": 1, "B": 5, "C": 3}) == {"A": 0.0, "B": 1.0, "C": 0.5}
    assert kf.normalize_min_max({"A": 7, "B": 7}) == {"A": 0.5, "B": 0.5}
    assert kf.normalize_min_max({}) == {}
