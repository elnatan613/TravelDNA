"""
שלד לשליפת עלות חיים מ-Numbeo, לחישוב ציר budget_vs_luxury.

Numbeo לא נותן API חינמי מלא - יש כמה אפשרויות:
1. Numbeo API בתשלום (הכי אמין)
2. גרידה ידנית של דפי העיר (numbeo.com/cost-of-living/in/<city>) - לבדוק תנאי שימוש
3. מאגר CSV חינמי שהם מפרסמים לפרויקטים לא-מסחריים - לבדוק בדף שלהם

TODO: להחליט על השיטה ולממש. כרגע מחזיר ערכי דמה כדי שהתאמה (matcher.py)
תוכל להתקדם בלי לחכות.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CITIES


def get_budget_score_dummy(city_name: str) -> float:
    """ערך דמה זמני - להחליף בשליפה אמיתית."""
    return 0.5


def get_budget_score(city_name: str) -> float:
    """
    TODO: לממש שליפה אמיתית מ-Numbeo.
    ציון 0 = תקציבי מאוד, 1 = יוקרתי/יקר מאוד.
    צריך לנרמל לפי מדד עלות חיים ביחס לשאר הערים ברשימה (לא מספר מוחלט).
    """
    return get_budget_score_dummy(city_name)


if __name__ == "__main__":
    for city in CITIES:
        print(f"{city}: {get_budget_score(city)}")
