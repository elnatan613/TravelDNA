"""
מנוע ההתאמה - מקבל פרופיל מטייל (וקטור + משקלים, ואופציונלית אילוץ כשרות
בוליארי) ורשימת יעדים מתויגים, ומחזיר את היעדים המדורגים לפי התאמה
(מהטוב ביותר).

כשרות (kosher_availability) היא constraint, לא ציר משוקלל - ראו
rank_destinations(requires_kosher=...): זה סינון קשה שקורה *לפני* חישוב
המרחק המשוקלל על 7 הצירים, לא עונש רך כמו שאר הצירים.

זה לא תלוי במודל ה-NLP - אפשר לפתח ולבדוק את זה במקביל עם ערכי דמה
מ-nlp.profile_extractor.extract_profile_dummy.
"""

import json
import math
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AXES, KOSHER_AVAILABILITY_THRESHOLD


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


def rank_destinations(
    traveler_vector: dict,
    weights: dict,
    destinations: list[dict],
    requires_kosher: bool = False,
    kosher_threshold: float = KOSHER_AVAILABILITY_THRESHOLD,
) -> list[dict]:
    """
    destinations: רשימת dict-ים, כל אחד עם מפתח "axes" (הציונים) ומפתח "city" (שם)
    (בדיוק הפורמט שמייצר scripts/destination_scraper.py)

    requires_kosher: האילוץ הבוליארי מצד המשתמש (kosher: true/false ב-config.py) -
    *לא* עוד ציר במרחק המשוקלל. אם True, מסננים החוצה יעדים עם kosher_availability
    נמוך מ-kosher_threshold *לפני* חישוב הדירוג - סינון קשה (hard filter), לא
    עונש רך כמו שאר הצירים. יעד בלי שדה kosher_availability בכלל (דאטה ישן/חסר)
    מטופל כ-0.0 (הכי מחמיר) כדי לא "לדלג" על הסינון בגלל דאטה חסר בשקט.

    kosher_threshold: מ-config.KOSHER_AVAILABILITY_THRESHOLD כברירת מחדל.

    מחזיר את היעדים שעברו את הסינון (אם requires_kosher), ממוינים מהכי
    מתאים לפחות מתאים, עם שדה נוסף "distance". אם אף יעד לא עומד בסינון -
    מחזיר רשימה ריקה (לא קורס).
    """
    candidates = destinations
    if requires_kosher:
        candidates = [
            dest for dest in destinations
            if dest.get("kosher_availability", 0.0) >= kosher_threshold
        ]

    scored = []
    for dest in candidates:
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
        {"city": "Prague", "axes": {**{a: 0.5 for a in AXES}, "urban": 0.85, "nightlife": 0.7}, "kosher_availability": 0.6},
        {"city": "Reykjavik", "axes": {**{a: 0.5 for a in AXES}, "urban": 0.15, "nightlife": 0.1}, "kosher_availability": 0.0},
    ]

    print("בלי דרישת כשרות:")
    for r in rank_destinations(sample_traveler, sample_weights, sample_destinations):
        print(f"  {r['city']}: מרחק {r['distance']}")

    print("\nעם דרישת כשרות (kosher=True) - רייקיאוויק (0.0) צריכה להיפסל:")
    for r in rank_destinations(sample_traveler, sample_weights, sample_destinations, requires_kosher=True):
        print(f"  {r['city']}: מרחק {r['distance']}")
