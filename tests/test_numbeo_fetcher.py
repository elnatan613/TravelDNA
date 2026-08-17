"""
בדיקות יחידה ל-scripts/numbeo_fetcher.py.

לא פוגעות ברשת (הדאטה סטטי, נאסף ידנית - ראו הדוקסטרינג של הקובץ) - בודקות
רק את לוגיקת הנרמול וההתאמה לכיוון שמוגדר ב-config.py.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)
sys.path.append(os.path.join(_PROJECT_ROOT, "scripts"))

from numbeo_fetcher import get_budget_score, NUMBEO_COST_OF_LIVING_INDEX
from config import CITIES


def test_all_known_cities_have_a_score_in_unit_range():
    for city in NUMBEO_COST_OF_LIVING_INDEX:
        score = get_budget_score(city)
        assert 0.0 <= score <= 1.0


def test_all_config_cities_covered():
    # כל עיר ב-config.CITIES צריכה להיות בטבלה - אם לא, זו אזהרה שהטבלה
    # לא עודכנה מאז שהתווספה עיר חדשה (ראו TODO בדוקסטרינג של numbeo_fetcher.py)
    missing = [c for c in CITIES if c not in NUMBEO_COST_OF_LIVING_INDEX]
    assert not missing, f"ערים ב-config.CITIES בלי ערך ב-NUMBEO_COST_OF_LIVING_INDEX: {missing}"


def test_direction_cheap_city_scores_higher_than_expensive_city():
    # Reykjavik הוא ה-Cost of Living Index הגבוה ביותר בטבלה (הכי יקרה),
    # Porto הוא הנמוך ביותר (הכי זולה) - לפי config.py, price_sensitivity
    # 0=יוקרתי, 1=תקציבי, אז Porto חייבת לקבל ציון גבוה יותר מ-Reykjavik.
    assert get_budget_score("Porto") > get_budget_score("Reykjavik")


def test_most_expensive_city_scores_near_zero():
    most_expensive = max(NUMBEO_COST_OF_LIVING_INDEX, key=NUMBEO_COST_OF_LIVING_INDEX.get)
    assert get_budget_score(most_expensive) == 0.0


def test_cheapest_city_scores_near_one():
    cheapest = min(NUMBEO_COST_OF_LIVING_INDEX, key=NUMBEO_COST_OF_LIVING_INDEX.get)
    assert get_budget_score(cheapest) == 1.0


def test_unknown_city_returns_neutral_default():
    assert get_budget_score("Atlantis") == 0.5
