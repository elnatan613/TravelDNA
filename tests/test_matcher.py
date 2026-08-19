"""
בדיקות יחידה למנוע ההתאמה (matching/matcher.py).

לא פוגעות ברשת בכלל - matcher.py לא תלוי ב-API-ים חיצוניים, רק בחשבון
מתמטי על וקטורים. יש כאן גם בדיקת אינטגרציה קלה נגד data/processed/
destinations.json האמיתי (ראו test_load_destinations_reads_real_file).
"""

import math
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)

from matching.matcher import weighted_distance, rank_destinations, load_destinations
from config import AXES, KOSHER_AVAILABILITY_THRESHOLD


def _uniform(value=0.5):
    """עוזר לבדיקות: וקטור עם אותו ערך על כל 7 הצירים."""
    return {axis: value for axis in AXES}


def test_weighted_distance_identical_vectors_is_zero():
    v = _uniform(0.5)
    assert weighted_distance(v, v, _uniform(1.0)) == 0.0


def test_weighted_distance_matches_manual_calculation():
    traveler = {**_uniform(0.5), "urban": 0.2}
    destination = {**_uniform(0.5), "urban": 0.8}
    weights = _uniform(1.0)

    # רק ציר urban שונה (0.2 מול 0.8) - שאר הצירים זהים ולא תורמים למרחק
    expected = math.sqrt(1.0 * (0.2 - 0.8) ** 2)
    assert weighted_distance(traveler, destination, weights) == pytest.approx(expected)


def test_weighted_distance_missing_axis_defaults_to_half():
    # אם ציר חסר לגמרי בוקטור (למשל דאטה חסר) - מתייחסים אליו כ-0.5, לא קורס
    traveler = {"urban": 0.5}  # שאר 6 הצירים חסרים
    destination = {"urban": 0.5}  # גם כאן
    weights = _uniform(1.0)
    assert weighted_distance(traveler, destination, weights) == 0.0


def test_weighted_distance_missing_weight_defaults_to_one():
    traveler = {**_uniform(0.5), "urban": 0.0}
    destination = {**_uniform(0.5), "urban": 1.0}
    weights = {}  # כל המשקלים חסרים - כולם צריכים לברור מחדל ל-1.0
    assert weighted_distance(traveler, destination, weights) == pytest.approx(1.0)


def test_weighted_distance_higher_weight_increases_distance_contribution():
    traveler = {**_uniform(0.5), "urban": 0.0}
    destination = {**_uniform(0.5), "urban": 1.0}
    low_weight_dist = weighted_distance(traveler, destination, {**_uniform(1.0), "urban": 1.0})
    high_weight_dist = weighted_distance(traveler, destination, {**_uniform(1.0), "urban": 4.0})
    assert high_weight_dist > low_weight_dist


def test_rank_destinations_orders_closest_first():
    traveler = {**_uniform(0.5), "urban": 0.9, "nightlife": 0.1}
    weights = {**_uniform(1.0), "urban": 2.0}

    destinations = [
        {"city": "Reykjavik", "axes": {**_uniform(0.5), "urban": 0.1, "nightlife": 0.05}},
        {"city": "Berlin", "axes": {**_uniform(0.5), "urban": 0.95, "nightlife": 0.9}},
    ]

    ranked = rank_destinations(traveler, weights, destinations)
    assert [r["city"] for r in ranked] == ["Berlin", "Reykjavik"]
    assert ranked[0]["distance"] <= ranked[1]["distance"]


def test_rank_destinations_preserves_original_fields_without_mutating_input():
    destinations = [
        {"city": "Paris", "country": "France", "axes": _uniform(0.5), "kosher_availability": 1.0},
    ]
    original_copy = json_safe_copy(destinations)

    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), destinations)

    assert ranked[0]["city"] == "Paris"
    assert ranked[0]["country"] == "France"
    assert ranked[0]["kosher_availability"] == 1.0
    assert "distance" in ranked[0]
    # rank_destinations לא אמור לשנות את הרשימה/dict-ים המקוריים שהועברו לו
    assert destinations == original_copy


def test_rank_destinations_empty_list_returns_empty():
    assert rank_destinations(_uniform(0.5), _uniform(1.0), []) == []


def _kosher_destinations():
    return [
        {"city": "Paris", "axes": _uniform(0.5), "kosher_availability": 0.9},
        {"city": "Reykjavik", "axes": _uniform(0.5), "kosher_availability": 0.0},
        {"city": "NoKosherField", "axes": _uniform(0.5)},  # דאטה ישן/חסר בכוונה
    ]


def test_requires_kosher_false_does_not_filter_anything():
    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), _kosher_destinations(), requires_kosher=False)
    assert len(ranked) == 3


def test_requires_kosher_true_filters_out_cities_below_threshold():
    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), _kosher_destinations(), requires_kosher=True)
    cities = {r["city"] for r in ranked}
    assert cities == {"Paris"}


def test_requires_kosher_true_treats_missing_field_as_zero_not_a_free_pass():
    # "NoKosherField" לא מציין kosher_availability בכלל - צריך להיחשב 0.0
    # (הכי מחמיר) ולהיפסל, לא "לדלג" על הסינון כי הדאטה חסר.
    destinations = [{"city": "NoKosherField", "axes": _uniform(0.5)}]
    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), destinations, requires_kosher=True)
    assert ranked == []


def test_requires_kosher_custom_threshold_is_respected():
    destinations = [{"city": "Middling", "axes": _uniform(0.5), "kosher_availability": 0.5}]
    # מעל הסף המרוכך (0.4) - נכנס
    assert len(rank_destinations(_uniform(0.5), _uniform(1.0), destinations, requires_kosher=True, kosher_threshold=0.4)) == 1
    # מתחת לסף המחמיר (0.6) - נפסל
    assert rank_destinations(_uniform(0.5), _uniform(1.0), destinations, requires_kosher=True, kosher_threshold=0.6) == []


def test_requires_kosher_default_threshold_matches_config():
    destinations = [
        {"city": "JustBelow", "axes": _uniform(0.5), "kosher_availability": KOSHER_AVAILABILITY_THRESHOLD - 0.01},
        {"city": "JustAtThreshold", "axes": _uniform(0.5), "kosher_availability": KOSHER_AVAILABILITY_THRESHOLD},
    ]
    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), destinations, requires_kosher=True)
    assert [r["city"] for r in ranked] == ["JustAtThreshold"]


def test_requires_kosher_all_filtered_out_returns_empty_not_crash():
    destinations = [{"city": "TooLow", "axes": _uniform(0.5), "kosher_availability": 0.0}]
    assert rank_destinations(_uniform(0.5), _uniform(1.0), destinations, requires_kosher=True) == []


def test_load_destinations_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_destinations("data/processed/no_such_file.json")


def test_load_destinations_reads_real_file():
    # בדיקת אינטגרציה קלה נגד הדאטה האמיתי שכן קיים בריפו
    path = os.path.join(_PROJECT_ROOT, "data", "processed", "destinations.json")
    destinations = load_destinations(path)

    assert len(destinations) == 18
    for dest in destinations:
        assert set(dest["axes"].keys()) == set(AXES)
        assert 0.0 <= dest["kosher_availability"] <= 1.0

    # ולוודא שכל הפייפליין (load + rank) עובד מקצה לקצה על הדאטה האמיתי
    ranked = rank_destinations(_uniform(0.5), _uniform(1.0), destinations)
    assert len(ranked) == 18
    assert ranked[0]["distance"] <= ranked[-1]["distance"]


def json_safe_copy(obj):
    import copy
    return copy.deepcopy(obj)
