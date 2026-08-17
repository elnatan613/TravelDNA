"""
סקריפט לאיסוף דאטה גולמי על יעדים (ערים) ותרגומו לציונים על צירי הפרופיל.

מקורות דאטה:
1. GeoNames - מידע גיאוגרפי בסיסי (אוכלוסיה, קואורדינטות) - חינמי לגמרי
   הרשמה: https://www.geonames.org/login
2. OpenTripMap - נקודות עניין (אטרקציות, טבע, תרבות, בילוי) - חינמי בשכבה בסיסית
   הרשמה: https://opentripmap.io/product

תרגום ביקורות (לשלב הבא, כשעוברים לביקורות גוגל בשפות זרות):
   משתמשים בספריית deep-translator, שמפעילה את המנוע של גוגל טרנסלייט
   בלי צורך במפתח API ובחינם לגמרי (יש הגבלת קצב, לא הגבלת כמות).
   התקנה: pip install deep-translator

שימוש:
    python destination_scraper.py

הפלט: קובץ destinations.json עם ציון 0-1 לכל עיר על כל ציר.
"""

import requests
import json
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CITIES  # מקור אמת יחיד לרשימת הערים - מוגדר ב-config.py

try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False


def translate_to_english(text, source_lang="auto"):
    """
    מתרגם טקסט (למשל ביקורת גוגל בצרפתית/גרמנית) לאנגלית, בחינם.
    מחזיר את הטקסט המקורי אם התרגום נכשל או אם הספרייה לא מותקנת.
    שימושי לפני הרצת מודל ה-NLP על ביקורות בשפות זרות.
    """
    if not TRANSLATION_AVAILABLE:
        print("deep-translator לא מותקן - מריץ 'pip install deep-translator'")
        return text
    try:
        return GoogleTranslator(source=source_lang, target="en").translate(text)
    except Exception as e:
        print(f"תרגום נכשל: {e}")
        return text

# ---- הגדרות - הכנס כאן את המפתחות שקיבלת בהרשמה ----
GEONAMES_USERNAME = "YOUR_GEONAMES_USERNAME"
OPENTRIPMAP_API_KEY = "YOUR_OPENTRIPMAP_KEY"

# רשימת הערים מוגדרת כעת ב-config.py (מקור אמת יחיד לשני חלקי הפרויקט)

# קטגוריות OpenTripMap שממפות לצירים שלנו
# (הרשימה המלאה של הקטגוריות נמצאת ב: https://opentripmap.io/catalog)
CATEGORY_MAP = {
    "urban_nature": {
        "urban": ["urban_environment", "architecture", "cultural"],
        "nature": ["natural", "geological_formations", "gardens_and_parks"],
    },
    "culture_nightlife": {
        "culture": ["historic", "cultural", "museums"],
        "nightlife": ["adult", "amusements", "sport"],
    },
}


def get_city_coordinates(city_name):
    """שולף קואורדינטות ומידע בסיסי מ-GeoNames לפי שם עיר."""
    url = "http://api.geonames.org/searchJSON"
    params = {
        "q": city_name,
        "maxRows": 1,
        "username": GEONAMES_USERNAME,
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if not data.get("geonames"):
        return None
    result = data["geonames"][0]
    return {
        "name": result["name"],
        "lat": float(result["lat"]),
        "lng": float(result["lng"]),
        "population": result.get("population", 0),
        "country": result.get("countryName", ""),
    }


def count_pois_by_category(lat, lng, category, radius=10000):
    """סופר כמה נקודות עניין מקטגוריה מסוימת יש ברדיוס נתון (במטרים) מסביב לעיר."""
    url = "https://api.opentripmap.com/0.1/en/places/radius"
    params = {
        "radius": radius,
        "lon": lng,
        "lat": lat,
        "kinds": category,
        "limit": 500,
        "apikey": OPENTRIPMAP_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        return 0
    data = resp.json()
    return len(data.get("features", []))


def compute_axis_score(city_coords, kinds_a, kinds_b):
    """
    מחשב ציון 0-1 על ציר דו-קוטבי (למשל עירוני מול טבע), לפי יחס בין
    ספירת POIs בקטגוריות של קצה א' מול קצה ב'.
    ציון קרוב ל-1 = נוטה לקטגוריה ב', קרוב ל-0 = נוטה לקטגוריה א'.
    """
    count_a = sum(
        count_pois_by_category(city_coords["lat"], city_coords["lng"], k)
        for k in kinds_a
    )
    count_b = sum(
        count_pois_by_category(city_coords["lat"], city_coords["lng"], k)
        for k in kinds_b
    )
    total = count_a + count_b
    if total == 0:
        return 0.5  # אין מספיק דאטה - ציון ניטרלי
    return round(count_b / total, 2)


def build_destination_profile(city_name):
    """בונה פרופיל מלא לעיר אחת - כל הצירים הרלוונטיים."""
    coords = get_city_coordinates(city_name)
    if not coords:
        print(f"לא נמצאו קואורדינטות עבור {city_name}, מדלג")
        return None

    print(f"מעבד את {city_name}...")

    urban_vs_nature = compute_axis_score(
        coords,
        CATEGORY_MAP["urban_nature"]["urban"],
        CATEGORY_MAP["urban_nature"]["nature"],
    )
    culture_vs_nightlife = compute_axis_score(
        coords,
        CATEGORY_MAP["culture_nightlife"]["culture"],
        CATEGORY_MAP["culture_nightlife"]["nightlife"],
    )

    time.sleep(1)  # לא להציף את ה-API בבקשות

    return {
        "city": coords["name"],
        "country": coords["country"],
        "lat": coords["lat"],
        "lng": coords["lng"],
        "axes": {
            "urban_vs_nature": urban_vs_nature,
            "culture_vs_nightlife": culture_vs_nightlife,
            # TODO: תקציב-יוקרה יתווסף בנפרד ממקור אחר (Numbeo)
            # TODO: כשרות/קהילתיות יתווסף ממאגר חב"ד/מסעדות כשרות
        },
    }


def main():
    results = []
    for city in CITIES:
        profile = build_destination_profile(city)
        if profile:
            results.append(profile)

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "processed", "destinations.json",
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nהושלם! {len(results)} ערים נשמרו ב-{output_path}")


if __name__ == "__main__":
    main()
