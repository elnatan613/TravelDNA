"""
סקריפט לאיסוף דאטה גולמי על יעדים (ערים) ותרגומו לציונים על 7 צירי הפרופיל
(ראו config.py - AXES).

מקורות דאטה:
1. GeoNames - מידע גיאוגרפי בסיסי (אוכלוסיה, קואורדינטות) - חינמי לגמרי
   הרשמה: https://www.geonames.org/login
2. Overpass API (OpenStreetMap) - נקודות עניין (תרבות, בילוי, אוכל,
   אטרקציות) - חינמי לגמרי, בלי הרשמה ובלי API key בכלל.
   שירות ציבורי: https://overpass-api.de/api/interpreter
   (עברנו אליו מ-OpenTripMap: תהליך ההרשמה שלהם - כולל אימות מייל - נתקע
   שוב ושוב בשגיאת שרת 500 מהצד שלהם. Overpass נותן דאטה שקול, בלי לחכות
   לאף שירות חיצוני להתאושש)

הציר price_sensitivity לא מגיע מ-Overpass/GeoNames אלא מ-numbeo_fetcher.py
(Numbeo Cost of Living Index, נאסף ידנית - ראו שם). kosher_availability
(לא אחד מ-7 הצירים - שדה נוסף על היעד, ראו README) מגיע מ-kashrut_fetcher.py
(גם הוא מ-Overpass, בתי כנסת + מקומות diet:kosher=yes).

תרגום ביקורות (לשלב הבא, כשעוברים לביקורות גוגל בשפות זרות):
   משתמשים בספריית deep-translator, שמפעילה את המנוע של גוגל טרנסלייט
   בלי צורך במפתח API ובחינם לגמרי (יש הגבלת קצב, לא הגבלת כמות).
   התקנה: pip install deep-translator

שימוש:
    # (חד-פעמי) הגדר את מפתח GeoNames - Overpass לא דורש מפתח בכלל.
    # הכי פשוט: קובץ .env בשורש הפרויקט (כבר ב-.gitignore, לא ייכנס לגיט):
    #   GEONAMES_USERNAME=your_username
    # (אפשר גם כמשתנה סביבה - setx GEONAMES_USERNAME "..." ב-PowerShell/CMD -
    # אבל שימו לב: משתני סביבה שהוגדרו כך נראים רק לתהליכים/טרמינלים
    # *חדשים* שנפתחו אחרי ה-setx, לא לתהליכים שכבר היו פתוחים).
    python destination_scraper.py

הפלט: קובץ destinations.json עם ציון 0-1 לכל עיר על כל אחד מ-7 הצירים.
"""

import requests
import json
import time
import sys
import os

# חשוב ב-Windows: קונסולת CMD/PowerShell רגילה (לא מוגדרת ל-UTF-8) קורסת
# על print() של עברית (UnicodeEncodeError, codepage cp1252) - זה היה עוצר
# ריצה של 10-15 דקות באמצע. reconfigure עם errors="replace" מונע קריסה
# גם אם הקונסולה לא תציג את התווים בצורה מושלמת.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_PROJECT_ROOT)
sys.path.append(_SCRIPTS_DIR)

from config import CITIES, AXES  # מקור אמת יחיד לרשימת הערים ולשמות הצירים
from numbeo_fetcher import get_budget_score  # ציר price_sensitivity
from kashrut_fetcher import compute_jewish_community_scores  # kosher_availability - לא ציר, שדה נוסף

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


def _load_dotenv_file(path):
    """
    טוען משתני סביבה מקובץ .env פשוט (KEY=VALUE בכל שורה, # להערות) אל
    os.environ, אם עדיין לא מוגדרים שם. לא דורס משתנה סביבה שכבר קיים.
    לא משתמשים בספריית python-dotenv כדי לא להוסיף תלות רק בשביל זה.
    """
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


# ---- מפתח API - נטען ממשתנה סביבה או מקובץ .env בשורש הפרויקט, עם ----
# ---- placeholder כברירת מחדל אם שניהם חסרים ----
# לא לשמור מפתחות אמיתיים בקוד/בגיט - .env כבר ב-.gitignore.
# Overpass (OSM) לא דורש שום מפתח.
_load_dotenv_file(os.path.join(_PROJECT_ROOT, ".env"))
GEONAMES_USERNAME = os.environ.get("GEONAMES_USERNAME", "YOUR_GEONAMES_USERNAME")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# חשוב: Overpass (Apache) מחזיר 406 Not Acceptable ל-User-Agent הגנרי של
# python-requests (כנראה חסימת בוטים בסיסית) - חובה לשלוח User-Agent מזוהה.
OVERPASS_HEADERS = {"User-Agent": "TravelDNA-destination-scraper/1.0", "Accept": "*/*"}

# מרווח בין קריאות API עוקבות, כדי לא לחצות מגבלות קצב (חשוב במיוחד עבור
# Overpass - זה שירות ציבורי-קהילתי עם מדיניות שימוש הוגן)
REQUEST_DELAY_SECONDS = 1.0

# כמה פעמים לנסות שוב שאילתת Overpass לעיר אחת אם נכשלה (502/504/timeout
# זמניים הם שכיחים בשירות הציבורי הזה)
OVERPASS_MAX_RETRIES = 3

# רדיוס קבוע (מטרים) לכל הערים - חשוב שיהיה אחיד כדי שההשוואה בין ערים
# (ובעיקר הנרמול היחסי למטה) תהיה הוגנת. 6 ק"מ ולא 10 - במטרופולינים
# גדולים (פריז, רומא) שאילתה על 10 ק"מ שלמים חצתה את מגבלת הזמן של Overpass.
POI_RADIUS_METERS = 6000

# timeout פנימי לשאילתת Overpass עצמה (בשניות) - חשוב שה-timeout של requests.post
# (ראו fetch_raw_counts) יהיה גבוה מזה, כדי לא לקצץ את הבקשה מהצד שלנו
# לפני שהשרת בכלל סיים.
OVERPASS_QUERY_TIMEOUT_SECONDS = 60

# רשימת הערים מוגדרת כעת ב-config.py (מקור אמת יחיד לשני חלקי הפרויקט)

# מיפוי צירים לתגי OpenStreetMap (Overpass QL)
# (קטלוג התגים המלא: https://wiki.openstreetmap.org/wiki/Map_features)
#
# "urban" (0=טבע/כפר, 1=עיר) מחושב מ-population של GeoNames, לא מ-Overpass -
# ראו main(). ניסינו בהתחלה יחס landuse עירוני/טבעי (POI-based),
# אבל זה התברר לא אמין: תיוג landuse ב-OSM לא עקבי - פארקים/יערות/מים
# מתויגים כפוליגונים גדולים ועקביים, אבל מרכזי ערים עתיקים וצפופים (כמו
# מרכז פריז) הרבה פעמים כלל לא מתויגים ב-landuse=residential/commercial
# (המידע כבר "מובלע" בבניינים הבודדים) - זה נתן לפריז ציון urban נמוך יותר
# מרייקיאוויק, הפוך מהמציאות. population היא מדד סטנדרטי ופשוט יותר
# ל"עד כמה זו עיר גדולה/עירונית", וגם חוסכת קריאת Overpass נוספת.
#
# שאר הצירים (culture, nightlife, food, social) הם חד-קוטביים - "כמה מזה יש
# בעיר" - ולכן מחושבים כספירת POIs גולמית, ומנורמלים בהמשך (min-max) יחסית
# לכל הערים שנאספו בהרצה הזו (לא לפי מספר מוחלט - בדיוק כמו הגישה שמתוארת
# ב-numbeo_fetcher.py לגבי price_sensitivity).
#
# כל ערך ברשימות למטה הוא תבנית Overpass QL יחידה (node+way) על תג מסוים;
# מריצים את כולן במחובר בשאילתה אחת לכל עיר (ראו build_overpass_query).
COUNT_BASED_AXIS_TAG_QUERIES = {
    "culture": ['["historic"]', '["tourism"~"museum|gallery|artwork"]'],
    "nightlife": ['["amenity"~"bar|pub|nightclub"]'],
    "food": ['["amenity"~"restaurant|cafe|fast_food"]'],
    # "social" - אין מקור דאטה ישיר ל"כמה חברתי/מפגשי" היעד. פרוקסי מקורב:
    # סכום ספירות בילוי+אוכל (מקומות שבהם אנשים נפגשים). TODO: לשפר בעתיד,
    # למשל עם ניתוח NLP על ביקורות גוגל ("atmosphere", "crowded", "social").
}

# "activity_density" - תג tourism=* רחב ב-OSM שמכיל כל אטרקציית תיירות
# (מוזיאונים, נקודות תצפית, בתי מלון וכו'). פרוקסי סביר ל"כמה יש לעשות
# בעיר" - גם הוא מנורמל min-max בהמשך.
ACTIVITY_DENSITY_TAG_QUERIES = ['["tourism"]']


def get_city_coordinates(city_name, max_retries=3):
    """
    שולף קואורדינטות ומידע בסיסי מ-GeoNames לפי שם עיר.

    עם ניסיונות חזרה על תקלות רשת זמניות (DNS/connection reset וכו') - בלי
    זה, תקלת רשת חד-פעמית באמצע ריצה של 15-20 דקות הייתה מפילה את כל
    התהליך (בדיוק מה שקרה בפועל: DNS resolution נכשל לרגע על עיר אחת
    והריצה השלמה קרסה, בזמן שהקריאות ל-Overpass כבר היו מוגנות retry).
    מחזיר None גם אם GeoNames לא מצא את העיר וגם אם כל הניסיונות נכשלו.
    """
    url = "http://api.geonames.org/searchJSON"
    params = {
        "q": city_name,
        "maxRows": 1,
        "username": GEONAMES_USERNAME,
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            time.sleep(REQUEST_DELAY_SECONDS)
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
        except (requests.RequestException, ValueError) as e:
            print(f"  אזהרה: קריאה ל-GeoNames נכשלה עבור {city_name} ({e}) (ניסיון {attempt + 1}/{max_retries})")
            time.sleep(REQUEST_DELAY_SECONDS * 2)
    return None


def _build_set_clause(set_name, tag_filters, lat, lng, radius):
    """בונה סניף Overpass QL יחיד: איחוד (node+way) לכל תגי הקטגוריה, לתוך סט בשם set_name."""
    lines = []
    for tag in tag_filters:
        lines.append(f'  node{tag}(around:{radius},{lat},{lng});')
        lines.append(f'  way{tag}(around:{radius},{lat},{lng});')
    body = "\n".join(lines)
    return f"(\n{body}\n)->.{set_name};"


def build_overpass_query(lat, lng, radius=POI_RADIUS_METERS):
    """
    בונה שאילתת Overpass QL אחת שסופרת בבת אחת את כל הקטגוריות הרלוונטיות
    לעיר (culture/nightlife/food/activity) - כדי לא לשלוח קריאת HTTP נפרדת
    לכל קטגוריה כמו שהיה מול OpenTripMap.
    """
    set_names = []
    clauses = []

    for set_name, tags in [
        ("culture", COUNT_BASED_AXIS_TAG_QUERIES["culture"]),
        ("nightlife", COUNT_BASED_AXIS_TAG_QUERIES["nightlife"]),
        ("food", COUNT_BASED_AXIS_TAG_QUERIES["food"]),
        ("activity", ACTIVITY_DENSITY_TAG_QUERIES),
    ]:
        clauses.append(_build_set_clause(set_name, tags, lat, lng, radius))
        set_names.append(set_name)

    out_lines = "\n".join(f".{name} out count;" for name in set_names)
    query = f"[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];\n" + "\n".join(clauses) + "\n" + out_lines
    return query, set_names


def fetch_raw_counts(coords, radius=POI_RADIUS_METERS, max_retries=OVERPASS_MAX_RETRIES):
    """
    שולף בקריאה אחת (שאילתת Overpass מרוכזת) את כל הספירות הגולמיות
    הדרושות לעיר אחת: culture, nightlife, food, activity.

    מחזיר (counts, success). אם success=False - כל הניסיונות נכשלו
    (Overpass הוא שירות ציבורי-קהילתי, יש לו תקלות זמניות: 429/502/504),
    ו-counts הוא רק ברירת מחדל (הכל 0) שלא מייצג דאטה אמיתי - חשוב
    להבחין בזה מ"0 אמיתי" (ראו main - קריאה חדשה ל-fetch_raw_counts
    בסוף עבור ערים שנכשלו, לא שימוש בברירת המחדל הזו כערך אמיתי).
    """
    query, set_names = build_overpass_query(coords["lat"], coords["lng"], radius)
    counts = {name: 0 for name in set_names}  # ברירת מחדל - לא דאטה אמיתי, רק placeholder

    for attempt in range(max_retries):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, headers=OVERPASS_HEADERS, timeout=OVERPASS_QUERY_TIMEOUT_SECONDS + 30)
            time.sleep(REQUEST_DELAY_SECONDS)
            if resp.status_code != 200:
                print(f"  אזהרה: Overpass החזיר סטטוס {resp.status_code} (ניסיון {attempt + 1}/{max_retries})")
                # 429 = חצינו rate limit - צריך לתת יותר זמן להתאוששות מ-504/502 רגיל
                time.sleep(REQUEST_DELAY_SECONDS * (6 if resp.status_code == 429 else 2))
                continue
            body = resp.json()
            if "remark" in body:
                # סטטוס 200 אבל Overpass עצמו נכשל (בד"כ timeout פנימי) - זו
                # לא הצלחה אמיתית, גם אם ה-HTTP status תקין
                print(f"  אזהרה: Overpass החזיר remark ({body['remark']}) (ניסיון {attempt + 1}/{max_retries})")
                time.sleep(REQUEST_DELAY_SECONDS * 2)
                continue
            elements = body.get("elements", [])
            # zip נעצר לפי הרשימה הקצרה יותר - אם Overpass החזיר פחות אלמנטים
            # ממה שביקשנו (למשל תקלה חלקית), רק החלק שהתקבל יעודכן והשאר יישאר 0
            for name, el in zip(set_names, elements):
                counts[name] = int(el.get("tags", {}).get("total", 0))
            return counts, True
        except (requests.RequestException, ValueError) as e:
            print(f"  אזהרה: שאילתת Overpass נכשלה ({e}) (ניסיון {attempt + 1}/{max_retries})")
            time.sleep(REQUEST_DELAY_SECONDS * 2)

    return counts, False


def normalize_min_max(city_to_raw_value: dict) -> dict:
    """
    מנרמל dict של {עיר: ערך גולמי} לסקאלה 0-1, יחסית למינימום/מקסימום
    שנמצאו בפועל בין הערים שנאספו (לא לפי ערך מוחלט קבוע מראש).
    אם כל הערים קיבלו את אותו ערך (או שהרשימה ריקה) - כולן מקבלות 0.5.
    """
    if not city_to_raw_value:
        return {}
    values = city_to_raw_value.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return {city: 0.5 for city in city_to_raw_value}
    return {
        city: round((val - lo) / (hi - lo), 2)
        for city, val in city_to_raw_value.items()
    }


def main():
    if GEONAMES_USERNAME == "YOUR_GEONAMES_USERNAME":
        print(
            "אזהרה: לא נמצא מפתח ב-GEONAMES_USERNAME כמשתנה סביבה - "
            "משתמש ב-placeholder, הקריאות ל-GeoNames ייכשלו.\n"
        )

    coords_by_city = {}
    raw_counts_by_city = {}
    failed_cities = []

    for city in CITIES:
        coords = get_city_coordinates(city)
        if not coords:
            print(f"לא נמצאו קואורדינטות עבור {city}, מדלג")
            continue

        print(f"מעבד את {city}...")
        coords_by_city[city] = coords
        counts, success = fetch_raw_counts(coords)
        raw_counts_by_city[city] = counts
        if not success:
            failed_cities.append(city)

    # סיבוב חזרה נוסף בסוף, רק לערים שנכשלו בכל 3 הניסיונות שלהן - בד"כ
    # תקלת עומס/rate-limit זמנית ב-Overpass שכבר חלפה עד שסיימנו עם שאר
    # הערים. חשוב: לא משתמשים בברירת המחדל (0) של fetch_raw_counts כאילו
    # היא דאטה אמיתי - זה היה גורם לערים שנכשלו לקבל ציון 0.0 מזויף בכל
    # הצירים הכמותיים (בדיוק הבאג שגילינו בהרצה קודמת: Lisbon/Berlin/
    # Copenhagen נכשלו ב-Overpass וקיבלו ציוני 0.0 כאילו זה נתון אמיתי).
    if failed_cities:
        print(f"\nמנסה שוב את הערים שנכשלו: {', '.join(failed_cities)}")
        time.sleep(REQUEST_DELAY_SECONDS * 10)  # לתת ל-Overpass זמן להתאושש
        still_failed = []
        for city in failed_cities:
            counts, success = fetch_raw_counts(coords_by_city[city], max_retries=OVERPASS_MAX_RETRIES + 2)
            raw_counts_by_city[city] = counts
            if not success:
                still_failed.append(city)
        if still_failed:
            print(
                f"\nאזהרה: לא הצלחתי לשלוף דאטה מ-Overpass בשביל: {', '.join(still_failed)} "
                "(גם אחרי סיבוב חזרה) - הערים האלה יוסרו מהפלט כדי לא לכתוב ציונים מזויפים."
            )
            for city in still_failed:
                del coords_by_city[city]
                del raw_counts_by_city[city]

    # ציר social - פרוקסי מקורב: סכום בילוי+אוכל (ראו הערה ב-COUNT_BASED_AXIS_TAG_QUERIES)
    for city, raw in raw_counts_by_city.items():
        raw["social"] = raw["nightlife"] + raw["food"]

    # נרמול min-max לכל הצירים הכמותיים, יחסית לכל הערים שנאספו בהצלחה בהרצה
    # הזו. "urban" מנורמל מ-population (GeoNames) - ראו הערה למעלה ב-
    # COUNT_BASED_AXIS_TAG_QUERIES על הסיבה שלא השתמשנו ב-POI ratio בשבילו.
    normalized_by_axis = {
        "urban": normalize_min_max(
            {city: coords_by_city[city]["population"] for city in coords_by_city}
        ),
    }
    for axis, raw_key in (
        ("culture", "culture"),
        ("nightlife", "nightlife"),
        ("food", "food"),
        ("social", "social"),
        ("activity_density", "activity"),
    ):
        normalized_by_axis[axis] = normalize_min_max(
            {city: raw_counts_by_city[city][raw_key] for city in raw_counts_by_city}
        )

    # kosher_availability - לא אחד מ-7 הצירים, שדה נוסף על היעד (ראו README).
    # מחושב בבת אחת לכל הערים (לא עיר-עיר) כי הציון מנורמל יחסית לכולן -
    # ראו compute_jewish_community_scores ב-kashrut_fetcher.py.
    kosher_scores = compute_jewish_community_scores(coords_by_city)

    results = []
    for city, coords in coords_by_city.items():
        axes_scores = {
            "urban": normalized_by_axis["urban"][city],
            "culture": normalized_by_axis["culture"][city],
            "nightlife": normalized_by_axis["nightlife"][city],
            "social": normalized_by_axis["social"][city],
            "activity_density": normalized_by_axis["activity_density"][city],
            "food": normalized_by_axis["food"][city],
            "price_sensitivity": get_budget_score(city),
        }
        assert set(axes_scores.keys()) == set(AXES), (
            f"axes_scores לא תואם ל-config.AXES: {sorted(axes_scores)} != {sorted(AXES)}"
        )
        results.append(
            {
                "city": coords["name"],
                "country": coords["country"],
                "lat": coords["lat"],
                "lng": coords["lng"],
                "axes": axes_scores,
                "kosher_availability": kosher_scores.get(city, 0.5),
            }
        )

    output_path = os.path.join(_PROJECT_ROOT, "data", "processed", "destinations.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nהושלם! {len(results)} ערים נשמרו ב-{output_path}")


if __name__ == "__main__":
    main()
