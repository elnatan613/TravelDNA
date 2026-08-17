"""
שלד לחישוב ציר jewish_community לכל עיר.

מקורות מתוכננים (לפי הדיון בתכנון):
1. מרחק לבית חב"ד הקרוב - Chabad.org (לבדוק אם יש API רשמי, אחרת גרידה זהירה)
2. מספר מסעדות כשרות מדווחות באזור
3. אזכורים בביקורות גוגל (Google Places API + מודל ה-NLP מ-nlp/, אחרי תרגום
   אם צריך - ראו scripts/destination_scraper.py -> translate_to_english)

TODO: לממש את שלושת המקורות ולשקלל אותם לציון אחד 0-1.
כרגע מחזיר ערכי דמה.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CITIES


def get_jewish_community_score_dummy(city_name: str) -> float:
    """ערך דמה זמני - להחליף בשליפה אמיתית."""
    return 0.5


def get_jewish_community_score(city_name: str) -> float:
    """
    TODO: לממש. ציון 0 = אין תשתית קהילתית, 1 = תשתית קהילתית עשירה מאוד.
    """
    return get_jewish_community_score_dummy(city_name)


if __name__ == "__main__":
    for city in CITIES:
        print(f"{city}: {get_jewish_community_score(city)}")
