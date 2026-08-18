"""
חישוב kosher_availability לכל עיר - לא אחד מ-7 הצירים (AXES), אלא שדה נוסף
על היעד (ראו README: כשרות היא constraint בצד המשתמש, לא ציר).
0 = אין תשתית קהילתית יהודית, 1 = תשתית עשירה מאוד.

מקורות שנשקלו ולמה לא:
1. Chabad.org - אין API רשמי ציבורי, וגרידה של האתר שלהם דורשת בדיקת ToS
   נפרדת שלא עשינו (בדיוק כמו עם Numbeo - ראו numbeo_fetcher.py).
2. Google Places API - דורש חשבון Google Cloud עם כרטיס אשראי/חיוב, לא
   מתאים לפרויקט גמר (ולא נבקש ממך פרטי תשלום).

מה שכן עשינו: OpenStreetMap (Overpass API, כמו ב-destination_scraper.py -
אותו מקור חינמי, בלי הרשמה) מתעד בפועל:
- בתי כנסת: amenity=place_of_worship + religion=jewish
- מקומות עם תיוג diet:kosher=yes (מסעדות, סופרמרקטים וכו')
בדקנו ידנית שהתוצאות הגיוניות (וינה: 8 בתי כנסת + 22 מקומות כשרים,
רייקיאוויק: 0+0) - קהילות יהודיות ידועות מיוצגות היטב ב-OSM.

חשוב: הקובץ הזה כפול חלק מהתשתית של destination_scraper.py (GEONAMES_USERNAME,
_load_dotenv_file, get_city_coordinates, OVERPASS_*, normalize_min_max) בכוונה,
כדי לא ליצור circular import בין שני קבצי ה-fetcher (destination_scraper.py
מייבא מהקובץ הזה את compute_jewish_community_scores).

שימוש עצמאי (עם המפתחות מ-.env/משתני סביבה, ראו destination_scraper.py):
    python kashrut_fetcher.py
"""

import requests
import json
import time
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_PROJECT_ROOT)
sys.path.append(_SCRIPTS_DIR)

from config import CITIES


def _load_dotenv_file(path):
    """טוען משתני סביבה מקובץ .env פשוט אל os.environ, אם עדיין לא מוגדרים."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv_file(os.path.join(_PROJECT_ROOT, ".env"))
GEONAMES_USERNAME = os.environ.get("GEONAMES_USERNAME", "YOUR_GEONAMES_USERNAME")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {"User-Agent": "TravelDNA-kashrut-fetcher/1.0", "Accept": "*/*"}
OVERPASS_QUERY_TIMEOUT_SECONDS = 60
OVERPASS_MAX_RETRIES = 3
REQUEST_DELAY_SECONDS = 1.0

# אותו רדיוס כמו destination_scraper.py, כדי שהתשתית הקהילתית תימדד באותו
# "מעגל" גיאוגרפי כמו שאר הצירים סביב מרכז העיר.
POI_RADIUS_METERS = 6000


def get_city_coordinates(city_name, max_retries=3):
    """
    שולף קואורדינטות מ-GeoNames (לשימוש עצמאי - ראו __main__ בסוף הקובץ).
    עם ניסיונות חזרה על תקלות רשת זמניות - ראו ההערה המקבילה ב-
    destination_scraper.get_city_coordinates.
    """
    url = "http://api.geonames.org/searchJSON"
    params = {"q": city_name, "maxRows": 1, "username": GEONAMES_USERNAME}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            time.sleep(REQUEST_DELAY_SECONDS)
            data = resp.json()
            if not data.get("geonames"):
                return None
            result = data["geonames"][0]
            return {"name": result["name"], "lat": float(result["lat"]), "lng": float(result["lng"])}
        except (requests.RequestException, ValueError) as e:
            print(f"  אזהרה: קריאה ל-GeoNames נכשלה עבור {city_name} ({e}) (ניסיון {attempt + 1}/{max_retries})")
            time.sleep(REQUEST_DELAY_SECONDS * 2)
    return None


def _build_overpass_query(lat, lng, radius=POI_RADIUS_METERS):
    return f"""[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];
(
  node["amenity"="place_of_worship"]["religion"="jewish"](around:{radius},{lat},{lng});
  way["amenity"="place_of_worship"]["religion"="jewish"](around:{radius},{lat},{lng});
)->.synagogue;
(
  node["diet:kosher"="yes"](around:{radius},{lat},{lng});
  way["diet:kosher"="yes"](around:{radius},{lat},{lng});
)->.kosher_food;
.synagogue out count;
.kosher_food out count;"""


def fetch_raw_kosher_counts(coords, radius=POI_RADIUS_METERS, max_retries=OVERPASS_MAX_RETRIES):
    """
    שולף מ-Overpass ספירה גולמית של בתי כנסת ומקומות עם diet:kosher=yes
    סביב עיר אחת. מחזיר (counts, success) - ראו fetch_raw_counts ב-
    destination_scraper.py להסבר מלא על למה מבחינים בין כשל להצלחה עם 0
    (לא רוצים שכשל-רשת יירשם כאילו הוא "0 קהילה יהודית" אמיתי).
    """
    query = _build_overpass_query(coords["lat"], coords["lng"], radius)
    counts = {"synagogue": 0, "kosher_food": 0}  # ברירת מחדל - לא דאטה אמיתי

    for attempt in range(max_retries):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, headers=OVERPASS_HEADERS, timeout=OVERPASS_QUERY_TIMEOUT_SECONDS + 30)
            time.sleep(REQUEST_DELAY_SECONDS)
            if resp.status_code != 200:
                print(f"  אזהרה: Overpass החזיר סטטוס {resp.status_code} (ניסיון {attempt + 1}/{max_retries})")
                time.sleep(REQUEST_DELAY_SECONDS * (6 if resp.status_code == 429 else 2))
                continue
            body = resp.json()
            if "remark" in body:
                print(f"  אזהרה: Overpass החזיר remark ({body['remark']}) (ניסיון {attempt + 1}/{max_retries})")
                time.sleep(REQUEST_DELAY_SECONDS * 2)
                continue
            elements = body.get("elements", [])
            for name, el in zip(("synagogue", "kosher_food"), elements):
                counts[name] = int(el.get("tags", {}).get("total", 0))
            return counts, True
        except (requests.RequestException, ValueError) as e:
            print(f"  אזהרה: שאילתת Overpass נכשלה ({e}) (ניסיון {attempt + 1}/{max_retries})")
            time.sleep(REQUEST_DELAY_SECONDS * 2)

    return counts, False


def normalize_min_max(city_to_raw_value: dict) -> dict:
    """זהה ל-normalize_min_max ב-destination_scraper.py - ראו שם להסבר מלא."""
    if not city_to_raw_value:
        return {}
    values = city_to_raw_value.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return {city: 0.5 for city in city_to_raw_value}
    return {city: round((val - lo) / (hi - lo), 2) for city, val in city_to_raw_value.items()}


def compute_jewish_community_scores(coords_by_city: dict) -> dict:
    """
    מחשב kosher_availability לכל הערים בבת אחת (לא עיר-עיר בנפרד) - כי
    הציון מנורמל *יחסית לכל הערים ברשימה*, בדיוק כמו שאר הצירים.

    coords_by_city: dict בפורמט {city_name: {"lat": ..., "lng": ...}} - את
    הקואורדינטות האלה destination_scraper.py כבר שלף מ-GeoNames, אז אין
    צורך לשלוף אותן שוב כאן (זה גם מה שמאפשר לקובץ הזה להיות עצמאי מ-
    destination_scraper.py, בלי circular import).

    מחזיר dict {city_name: score 0-1}. משקלל שווה בין שני המקורות (בתי כנסת
    ומקומות כשרים) - כל אחד מנורמל min-max בנפרד ואז ממוצע, כדי שמקור עם
    שונות גדולה יותר (למשל מקומות כשרים, שיש בהם הרבה יותר תיוג לא-עקבי
    ב-OSM) לא ישתלט על הציון הסופי.
    """
    raw_by_city = {}
    failed_cities = []
    for city, coords in coords_by_city.items():
        print(f"בודק תשתית יהודית ב-{city}...")
        counts, success = fetch_raw_kosher_counts(coords)
        raw_by_city[city] = counts
        if not success:
            failed_cities.append(city)

    still_failed = []
    if failed_cities:
        print(f"\nמנסה שוב את הערים שנכשלו: {', '.join(failed_cities)}")
        time.sleep(REQUEST_DELAY_SECONDS * 10)
        for city in failed_cities:
            counts, success = fetch_raw_kosher_counts(coords_by_city[city], max_retries=OVERPASS_MAX_RETRIES + 2)
            raw_by_city[city] = counts
            if not success:
                still_failed.append(city)
        if still_failed:
            print(
                f"\nאזהרה: לא הצלחתי לשלוף דאטה קהילתי בשביל: {', '.join(still_failed)} - "
                "יקבלו ציון ניטרלי (0.5) במקום לזייף '0 קהילה'."
            )

    # לא כוללים ערים שנכשלו סופית בנרמול - כדי שאפס-מזויף לא ימשוך את
    # שאר הערים (ראו הבדיקה למעלה - min/max יחסי לכל הערים שכן הצליחו)
    usable_cities = [city for city in raw_by_city if city not in still_failed]
    synagogue_scores = normalize_min_max({city: raw_by_city[city]["synagogue"] for city in usable_cities})
    kosher_food_scores = normalize_min_max({city: raw_by_city[city]["kosher_food"] for city in usable_cities})

    result = {}
    for city in coords_by_city:
        if city in synagogue_scores and city in kosher_food_scores:
            result[city] = round((synagogue_scores[city] + kosher_food_scores[city]) / 2, 2)
        else:
            result[city] = 0.5  # כשל שלא התאושש - ניטרלי, לא מזויף כ"0 קהילה"
    return result


if __name__ == "__main__":
    coords_by_city = {}
    for city in CITIES:
        coords = get_city_coordinates(city)
        if coords:
            coords_by_city[city] = coords
        else:
            print(f"לא נמצאו קואורדינטות עבור {city}, מדלג")

    scores = compute_jewish_community_scores(coords_by_city)
    print()
    for city in CITIES:
        print(f"{city}: {scores.get(city, 0.5)}")
