"""
מודול חילוץ פרופיל מטייל - גרסה מעודכנת לפי הארכיטקטורה:

Answers (שאלות סגורות 1-5)
    ↓
Rule-based mapping   <- אין AI כאן, זו המרה ליניארית פשוטה
    ↓
Base Profile
    ↓
Free text
    ↓
LLM                  <- ה-AI היחיד בשלב הזה, רק על הטקסט הפתוח
    ↓
Merge + Validation (clamp 0-1)
    ↓
Final Profile

חשוב: ה-LLM לא "מחליט" על כל הפרופיל, הוא רק מציע התאמות לחלק
שהתקבל מהטקסט החופשי. אסור לו "לשבור" scores שכבר נקבעו מהשאלות הסגורות
בלי בסיס בטקסט.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AXES


def closed_answers_to_profile(answers: dict) -> dict:
    """
    ממיר תשובות לשאלות סגורות (כל תשובה בסקאלה 1-5) לפרופיל בסיסי 0-1.
    זו המרה ליניארית פשוטה - אין כאן שום AI, זה rule-based בכוונה.

    answers: dict כמו {"urban": 3, "culture": 5, "nightlife": 2, ...}
    (המספרים הם מה שהמשתמש בחר בשאלון, 1 עד 5)
    """
    profile = {}
    for axis in AXES:
        raw = answers.get(axis)
        if raw is None:
            profile[axis] = 0.5  # לא נענה - ניטרלי
        else:
            profile[axis] = (raw - 1) / 4  # ממיר 1-5 ל-0-1
    return profile


def extract_adjustments_from_text_dummy(open_text: str) -> dict:
    """
    גרסת דמה - מחזירה dict ריק (אין התאמות), כדי שאפשר יהיה לבדוק
    את שאר הזרימה בלי לחכות למודל האמיתי.
    """
    return {}


def extract_adjustments_from_text(open_text: str) -> dict:
    """
    TODO: הפונקציה האמיתית - קוראת ל-LLM עם הטקסט הפתוח בלבד,
    ומבקשת ממנו להחזיר JSON עם *רק* הצירים שהוא בטוח שיש להם עדות בטקסט.
    לדוגמה, אם המשתמש כתב "אני אוהב ללכת הרבה ברגל, אוכל טוב חשוב לי",
    התשובה הצפויה: {"food": 0.9} - לא למלא את כל שאר הצירים בניחוש.

    כרגע קורא לגרסת הדמה, להחליף בהמשך.
    """
    return extract_adjustments_from_text_dummy(open_text)


def merge_and_validate(base_profile: dict, adjustments: dict) -> dict:
    """
    ממזג את הפרופיל הבסיסי (מהשאלות הסגורות) עם ההתאמות מה-LLM,
    ומוודא שכל ערך נשאר בטווח 0-1 (validation קריטי - LLM עלול להחזיר
    ערכים מחוץ לטווח, וזה חייב להיחתך).
    """
    merged = dict(base_profile)
    for axis, value in adjustments.items():
        if axis in AXES:
            merged[axis] = max(0.0, min(1.0, value))
    return merged


def build_travel_profile(closed_answers: dict, open_text: str) -> dict:
    """
    הפונקציה הראשית - מחברת את כל השלבים.
    closed_answers: תשובות השאלון הסגור (1-5 לכל ציר)
    open_text: התשובה החופשית של המשתמש
    """
    base = closed_answers_to_profile(closed_answers)
    adjustments = extract_adjustments_from_text(open_text)
    return merge_and_validate(base, adjustments)


def extract_importance_weights(slider_values: dict) -> dict:
    """
    ממיר את ערכי הסליידרים (1-5) שהמשתמש בחר, למשקלים בפועל.
    slider_values: dict כמו {"urban": 4, "price_sensitivity": 2, ...}
    """
    return {axis: slider_values.get(axis, 3) / 5 for axis in AXES}


if __name__ == "__main__":
    # דוגמה לבדיקה מהירה
    sample_closed_answers = {
        "urban": 2,       # נטה לטבע
        "culture": 4,
        "nightlife": 1,
        "social": 2,
        "activity_density": 3,
        "food": 5,
        "price_sensitivity": 3,
    }
    sample_text = "חשוב לי מאוד אוכל טוב, ואני לא אוהב מקומות תיירותיים מדי"

    profile = build_travel_profile(sample_closed_answers, sample_text)
    print("פרופיל לדוגמה:", profile)
