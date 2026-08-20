"""
Trip Planning Agent - הרכיב האחרון בזרימה מה-README:
"בחירת יעד + ימים + תקציב → RAG + Agent → מסלול טיול אישי".

זה ה-AI האמיתי הראשון בפרויקט (עד כה כל המקורות היו חינמיים/דטרמיניסטיים,
בלי LLM בכלל) - Gemini עם שני כלים (function calling):
1. search_knowledge - מחפש ב-rag/retriever.py (Paris/Prague/Vienna בלבד)
2. estimate_daily_budget - מחשב הערכת תקציב מ-scripts/numbeo_fetcher.py

למה Gemini ולא Claude/OpenAI: יש לו שכבת חינם אמיתית בלי כרטיס אשראי
(ai.google.dev) - עקבי עם כל שאר בחירות המקורות בפרויקט הזה.

איך זה עובד בפועל: משתמשים ב-"automatic function calling" של google-genai -
מעבירים פונקציות Python רגילות (עם type hints + docstring) כ-tools, וה-SDK
דואג בעצמו להריץ אותן כשהמודל מחליט לקרוא להן, ולהחזיר את התוצאה חזרה
למודל - לא צריך לכתוב לולאת tool-use ידנית.

שימוש עצמאי:
    python agent/trip_planner.py Paris 3 500
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(_PROJECT_ROOT, "scripts")
sys.path.append(_PROJECT_ROOT)
sys.path.append(_SCRIPTS_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from google import genai
from google.genai import types

from rag.retriever import Retriever, available_cities
from numbeo_fetcher import estimate_daily_cost_usd


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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash"

SYSTEM_INSTRUCTION = """You are a trip-planning assistant for the TravelDNA app.

You have two tools:
- search_knowledge: semantic search over a curated travel guide for one city.
  Call it several times with different focused queries (e.g. "top attractions",
  "food and restaurants", "getting around", "practical tips") to gather enough
  material BEFORE writing the itinerary. Only cities with a built knowledge base
  can be searched - if a city isn't available, say so plainly instead of
  inventing content.
- estimate_daily_budget: a rough average daily cost estimate (USD, excluding
  accommodation) for a city. Call it once and use it to sanity-check whether
  the traveler's stated budget is realistic for the requested number of days -
  explicitly say if the budget looks tight or generous.

When you write the day-by-day itinerary:
- Base factual claims (specific place names, practical details) ONLY on what
  search_knowledge actually returned - never invent a specific venue name that
  didn't come from a tool result.
- Structure the answer as one section per day.
- Keep it concise and practical, not flowery.
"""


class TripPlanningAgent:
    """
    עוטף client של Gemini + שני הכלים, וחושף plan_trip() כפעולה אחת.
    טוען את מודל ה-embeddings (Retriever) פעם אחת ב-__init__ - זה איטי
    (כמה שניות), לא רוצים לעשות את זה בכל קריאה ל-plan_trip.
    """

    def __init__(self, api_key: str | None = None, model: str = GEMINI_MODEL, retriever: Retriever | None = None):
        resolved_key = api_key or GEMINI_API_KEY
        if not resolved_key:
            raise RuntimeError(
                "אין GEMINI_API_KEY - הגדר אותו ב-.env בשורש הפרויקט "
                "(ראו https://aistudio.google.com/apikey לקבלת מפתח חינמי)"
            )
        self.client = genai.Client(api_key=resolved_key)
        self.model = model
        self.retriever = retriever or Retriever()

    def search_knowledge(self, city: str, query: str) -> str:
        """Search the curated travel knowledge base for a specific city.

        Args:
            city: exact city name (e.g. "Paris"). Only cities with a built
                knowledge base work - call this even for an unlisted city to
                get back the list of what IS available.
            query: what to look for, e.g. "best museums" or "local food".
        """
        try:
            results = self.retriever.retrieve(query, city, top_k=4)
        except FileNotFoundError:
            return f"No knowledge base for '{city}'. Available cities: {available_cities()}"
        if not results:
            return "No relevant information found for this query."
        return "\n\n".join(f"[{r['section']}] {r['text']}" for r in results)

    def estimate_daily_budget(self, city: str) -> str:
        """Estimate a rough average daily cost in USD for a tourist in a city
        (food, local transport, attraction tickets - excluding accommodation).

        Args:
            city: exact city name (e.g. "Paris").
        """
        cost = estimate_daily_cost_usd(city)
        if cost is None:
            return f"No cost-of-living data available for '{city}'."
        return f"Rough estimated daily cost in {city} (excluding accommodation): ${cost} USD."

    def plan_trip(self, city: str, days: int, budget_total_usd: float, preferences: str = "") -> str:
        """
        בונה מסלול יום-יום ל-city, days ימים, בתקציב הכולל שניתן.
        preferences: טקסט חופשי אופציונלי (למשל "אוהב אוכל, לא אוהב הליכה
        ארוכה") - ניתן לחבר בעתיד לפרופיל שמגיע מ-nlp/profile_extractor.py.
        """
        if city not in available_cities():
            return (
                f"אין בסיס ידע (RAG) עבור '{city}'. "
                f"כרגע נתמכות רק: {available_cities()} "
                "(ראו rag/build_knowledge_base.py כדי להוסיף עוד ערים)."
            )

        chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[self.search_knowledge, self.estimate_daily_budget],
            ),
        )
        prompt = (
            f"Plan a {days}-day trip to {city}. "
            f"Total budget: ${budget_total_usd} USD (excluding flights and accommodation). "
            f"Traveler preferences: {preferences or 'none given - keep it well-rounded'}."
        )
        response = chat.send_message(prompt)
        return response.text


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("שימוש: python agent/trip_planner.py <עיר> <ימים> <תקציב-דולר> [העדפות]")
        print(f"ערים זמינות (עם בסיס ידע): {available_cities()}")
        sys.exit(1)

    city_arg = sys.argv[1]
    days_arg = int(sys.argv[2])
    budget_arg = float(sys.argv[3])
    preferences_arg = " ".join(sys.argv[4:])

    agent = TripPlanningAgent()
    print(agent.plan_trip(city_arg, days_arg, budget_arg, preferences_arg))
