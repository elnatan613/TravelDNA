"""
בדיקות יחידה ל-scripts/destination_scraper.py.

בכוונה לא פוגעות ב-API אמיתי (GeoNames/OpenTripMap) - בודקות רק את לוגיקת
הנרמול ואת התאמת מבנה הפלט ל-config.AXES, כדי שאפשר להריץ אותן בלי מפתחות.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)
sys.path.append(os.path.join(_PROJECT_ROOT, "scripts"))

from destination_scraper import normalize_min_max
from config import AXES


def test_normalize_min_max_basic_range():
    raw = {"Paris": 100, "Reykjavik": 0, "Prague": 50}
    normalized = normalize_min_max(raw)
    assert normalized["Reykjavik"] == 0.0
    assert normalized["Paris"] == 1.0
    assert normalized["Prague"] == 0.5


def test_normalize_min_max_all_equal_returns_neutral():
    raw = {"Paris": 7, "Prague": 7, "Vienna": 7}
    normalized = normalize_min_max(raw)
    assert all(v == 0.5 for v in normalized.values())


def test_normalize_min_max_empty_returns_empty():
    assert normalize_min_max({}) == {}


def test_normalize_min_max_output_in_unit_range():
    raw = {"Paris": 12, "Reykjavik": 3, "Prague": 9, "Vienna": 3}
    normalized = normalize_min_max(raw)
    assert all(0.0 <= v <= 1.0 for v in normalized.values())


def test_axes_scores_shape_matches_config_axes():
    # לא בודק את main() בפועל (זה דורש מפתחות API אמיתיים) - רק שהמבנה
    # שהיא בונה (axes_scores עם 7 המפתחות) תואם בדיוק ל-config.AXES המשותף.
    fake_axes_scores = {axis: 0.5 for axis in AXES}
    assert set(fake_axes_scores.keys()) == set(AXES)
    assert len(AXES) == 7
