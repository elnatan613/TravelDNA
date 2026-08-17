"""
מנוע ההתאמה - מקבל פרופיל מטייל (וקטור + משקלים) ורשימת יעדים מתויגים,
ומחזיר את היעדים המדורגים לפי התאמה (מהטוב ביותר).

זה לא תלוי במודל ה-NLP - אפשר לפתח ולבדוק את זה במקביל עם ערכי דמה
מ-nlp.profile_extractor.extract_profile_dummy.
"""

import json
import math
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AXES


def weighted_distance(traveler_vector: dict, destination_vector: dict, weights: dict) -> float:
    """
    מחשב מרחק אוקלידי משוקלל בין וקטור מטייל לוקטור יעד.
    מרחק קטן יותר = התאמה טובה יותר.
    """
    total = 0.0
    for axis in AXES:
        t_val = traveler_vector.get(axis, 0.5)
        d_val = destination_vector.get(axis, 0.5)
        w = weights.get(axis, 1.0)
        total += w * (t_val - d_val) ** 2
    return math.sqrt(total)


def rank_destinations(traveler_vector: dict, weights: dict, destinations: list[dict]) -> list[dict]:
    """
    destinations: רשימת dict-ים, כל אחד עם מפתח "axes" (הציונים) ומפתח "city" (שם)
    (בדיוק הפורמט שמייצר scripts/destination_scraper.py)

    מחזיר את אותה רשימה, ממוינת מהכי מתאים לפחות מתאים, עם שדה נוסף "score".
    """
    scored = []
    for dest in destinations:
        dist = weighted_distance(traveler_vector, dest["axes"], weights)
        scored.append({**dest, "distance": round(dist, 3)})

    scored.sort(key=lambda d: d["distance"])
    return scored


def load_destinations(path: str = "data/processed/destinations.json") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    # דוגמה לבדיקה מהירה עם דאטה דמה - שימושי לפני שהדאטה האמיתי מוכן
    sample_traveler = {axis: 0.5 for axis in AXES}
    sample_traveler["urban"] = 0.2       # מעדיף טבע
    sample_traveler["nightlife"] = 0.1   # לא מעניין אותו בילוי

    sample_weights = {axis: 1.0 for axis in AXES}
    sample_weights["urban"] = 2.0  # קריטי למטייל הזה

    sample_destinations = [
        {"city": "Prague", "axes": {**{a: 0.5 for a in AXES}, "urban": 0.85, "nightlife": 0.7}},
        {"city": "Reykjavik", "axes": {**{a: 0.5 for a in AXES}, "urban": 0.15, "nightlife": 0.1}},
    ]

    results = rank_destinations(sample_traveler, sample_weights, sample_destinations)
    for r in results:
        print(f"{r['city']}: מרחק {r['distance']}")
