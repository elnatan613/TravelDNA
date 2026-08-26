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
from google import genai
import json


def _load_dotenv_file(path):
    """טוען משתני סביבה מקובץ .env פשוט אל os.environ."""
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            os.environ.setdefault(key, value)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_load_dotenv_file(os.path.join(_PROJECT_ROOT, ".env"))


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
    if not open_text or not open_text.strip():
        return {}

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    axes_description = """
    Available axes:

    - urban: preference for urban environments.
    0 = prefers nature/villages
    1 = strongly prefers cities

    - culture: interest in cultural sites, museums, history and cultural experiences.
    0 = low interest
    1 = very high interest

    - nightlife: interest in evening entertainment and nightlife.
    0 = low interest
    1 = very high interest

    - social: preference for social activities and meeting/interacting with people.
    0 = prefers quiet/independent activities
    1 = very social

    - activity_density: preference for having many activities during each day.
    0 = few activities / relaxed pace
    1 = many activities / packed days

    - food: importance of food and culinary experiences during the trip.
    0 = low importance
    1 = very high importance

    - price_sensitivity: sensitivity to price and preference for budget-friendly options.
    0 = price is not important / comfortable with expensive options
    1 = very price-sensitive / strongly prefers budget options
    """

    prompt = f"""
    You are a travel profile extraction system.

    Analyze the user's free-text travel description.

    Your task is to identify ONLY the travel preferences that are explicitly
    supported by the user's text.

    {axes_description}

    Rules:
    1. Return ONLY valid JSON.
    2. The JSON must be an object containing zero or more of the seven axes above.
    3. Include an axis ONLY when there is clear evidence for it in the user's text.
    4. Do NOT guess or infer preferences that are not clearly supported.
    5. Do NOT include axes that are not mentioned or supported.
    6. Every value must be a number between 0.0 and 1.0.
    7. A higher value means stronger preference for that axis.
    8. Do not include "kosher" or any other field that is not one of the seven axes.
    9. If the text provides no useful information about these axes, return {{}}.

    User text:
    {open_text}
    """

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
        },
    )

    try:
        adjustments = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(adjustments, dict):
        return {}

    validated = {}

    for axis, value in adjustments.items():
        if axis not in AXES:
            continue

        if not isinstance(value, (int, float)):
            continue

        if not 0.0 <= value <= 1.0:
            continue

        validated[axis] = float(value)

    return validated

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
