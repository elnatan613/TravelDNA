"""
חישוב ציר price_sensitivity (ראו config.py) מ-Numbeo Cost of Living Index.

למה לא scraping אוטומטי: Terms of Use של Numbeo אוסרים במפורש איסוף דאטה
אוטומטי (scraping/crawling) בלי אישור כתוב מראש -
https://www.numbeo.com/common/terms_of_use.jsp ("Automated data collection
methods ... are strictly prohibited unless you have obtained prior written
permission"). לכן הקוד הזה לא פונה ל-Numbeo ברשת בזמן ריצה בכלל.

למה לא ה-API הרשמי: Numbeo Data API הוא בתשלום בלבד, בלי שכבה חינמית -
מסלול הכניסה הזול ביותר הוא 260$/חודש (numbeo.com/common/api.jsp) - לא
רלוונטי לפרויקט גמר.

מה שכן עשינו: Numbeo מרשה במפורש "Academic Use" (thesis/עבודות אקדמיות)
של התוכן הציבורי שלהם בתנאי קרדיט (Terms of Use, סעיף "Academic Use").
לכן אספנו *ידנית* (לא באמצעות סקריפט/בוט) את ה-Cost of Living Index הציבורי
לכל אחת מ-18 הערים ב-config.CITIES, מתוך הדף הציבורי:
https://www.numbeo.com/cost-of-living/rankings.jsp (Europe, 2026 Mid-Year,
נאסף ב-2026-08-17) - וקבענו אותו כטבלה סטטית בקובץ הזה.

קרדיט (כנדרש ברישיון ה-Academic Use של Numbeo):
נתוני עלות החיים לקוחים מ-Numbeo.com - Cost of Living Index by City,
https://www.numbeo.com/cost-of-living/rankings.jsp

אם ב-config.CITIES תתווסף עיר חדשה שאינה ברשימה למטה - יש לעדכן את הטבלה
ידנית מהדף הציבורי (לא באוטומציה), או להסתפק בברירת המחדל הניטרלית (0.5).
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CITIES

# Numbeo Cost of Living Index (יחסי ל-New York City = 100.0) - נאסף ידנית
# ב-2026-08-17 מ-https://www.numbeo.com/cost-of-living/rankings.jsp
# (Europe, 2026 Mid-Year). ערך גבוה = יקר יותר.
NUMBEO_COST_OF_LIVING_INDEX = {
    "Paris": 78.4,
    "Barcelona": 59.9,
    "Amsterdam": 81.4,
    "Prague": 57.3,
    "Vienna": 74.5,
    "Reykjavik": 98.3,
    "Lisbon": 55.2,
    "Budapest": 55.5,
    "Krakow": 50.8,
    "Berlin": 72.5,
    "Rome": 60.0,
    "Florence": 71.0,
    "Copenhagen": 86.8,
    "Stockholm": 79.1,
    "Dublin": 76.3,
    "Edinburgh": 73.5,
    "Athens": 56.9,
    "Porto": 50.6,
}


def get_budget_score(city_name: str) -> float:
    """
    מחזיר את ציר price_sensitivity בדיוק כמו שהוא מוגדר ב-config.py:
    0 = יוקרתי/יקר מאוד (פחות רגיש למחיר), 1 = תקציבי מאוד (רגיש למחיר מאוד).

    מנרמל min-max הפוך על NUMBEO_COST_OF_LIVING_INDEX, יחסית לכל הערים
    שיש להן ערך בטבלה (לא לפי מספר מוחלט) - בדיוק כמו הנרמול שנעשה על שאר
    הצירים ב-scripts/destination_scraper.py (normalize_min_max): עיר עם
    Cost of Living Index גבוה יחסית (יקרה) מקבלת ציון קרוב ל-0, ועיר עם
    אינדקס נמוך יחסית (זולה) מקבלת ציון קרוב ל-1.

    אם העיר לא נמצאת בטבלה (למשל עיר חדשה שנוספה ל-config.CITIES ולא
    עודכנה כאן עדיין) - מחזיר 0.5 (ניטרלי), במקום לקרוס.
    """
    if city_name not in NUMBEO_COST_OF_LIVING_INDEX:
        return 0.5

    values = NUMBEO_COST_OF_LIVING_INDEX.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return 0.5

    index = NUMBEO_COST_OF_LIVING_INDEX[city_name]
    return round(1 - (index - lo) / (hi - lo), 2)


# הערכה גסה (לא תחזית מחיר אמיתית!) לתקציב יומי "בינוני" לתייר - אוכל,
# תחבורה מקומית, כניסות לאטרקציות - *לא* כולל לינה, בעיר במחיר NYC
# (Cost of Living Index = 100). מספר שרירותי-במידה, שרק נועד לתת לסוכן
# (agent/trip_planner.py) קנה מידה יחסי סביר בין ערים, לא הצעת מחיר אמיתית.
BASELINE_DAILY_COST_USD_AT_NYC_INDEX = 150.0


def estimate_daily_cost_usd(city_name: str) -> float | None:
    """
    מחזיר הערכה גסה לעלות יומית לתייר בעיר, ב-USD (בלי לינה) - סקלת
    NUMBEO_COST_OF_LIVING_INDEX כפול BASELINE_DAILY_COST_USD_AT_NYC_INDEX.
    לא מדויק, רק יחסי בין ערים. מחזיר None אם אין דאטה לעיר (לא 0 - כדי
    לא להטעות שהעיר "בחינם").
    """
    if city_name not in NUMBEO_COST_OF_LIVING_INDEX:
        return None
    index = NUMBEO_COST_OF_LIVING_INDEX[city_name]
    return round(BASELINE_DAILY_COST_USD_AT_NYC_INDEX * (index / 100), 1)


if __name__ == "__main__":
    for city in CITIES:
        print(f"{city}: price_sensitivity={get_budget_score(city)}, ~${estimate_daily_cost_usd(city)}/day")
