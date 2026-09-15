"""
Trip Planning Agent - הרכיב האחרון בזרימה מה-README:
"בחירת יעד + ימים + תקציב → RAG + Agent → מסלול טיול אישי".

זה ה-AI האמיתי הראשון בפרויקט (עד כה כל המקורות היו חינמיים/דטרמיניסטיים,
בלי LLM בכלל) - Gemini עם שני כלים (function calling):
1. search_knowledge - מחפש ב-rag/retriever.py (כל 18 הערים שב-config.CITIES)
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
import re

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(_PROJECT_ROOT, "scripts")
sys.path.append(_PROJECT_ROOT)
sys.path.append(_SCRIPTS_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from google import genai
from google.genai import types, errors

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
# The responsive Lite model is the default interactive experience. Keep 3.6
# available as a higher-capability fallback when Lite is temporarily unavailable.
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODEL = "gemini-3.6-flash"

SYSTEM_INSTRUCTION = """You are a trip-planning assistant for the TravelDNA app.

Write the entire final response in Hebrew, including headings, place names,
attraction names and currency names. Transliterate foreign proper nouns into
Hebrew when needed; do not append their English spelling in parentheses.
Only source URLs may contain Latin letters. Preserve source URLs exactly.
Write monetary amounts as numbers followed by Hebrew currency names, for
example "500 דולר" or "40 אירו". Do not use dollar signs or LaTeX math.

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
  search_knowledge or the live named venue candidate pool actually returned -
  never invent a specific venue name that did not come from either source.
- Every recommendation for an attraction must name one specific, identifiable
  venue: a particular museum, gallery, market, park, monument or viewpoint.
  “a gallery”, “the market”, “a museum”, “stroll downtown” and similar generic
  categories are not recommendations. Use the venue's proper name. If the
  search results do not contain a named venue, make that block flexible free
  time instead of pretending it is an attraction.
- For every named attraction, write a useful 2-3 sentence description: what
  the traveler will actually see or do, why it fits this itinerary, and the
  relevant neighbourhood, street or nearby landmark when it appears in the
  curated guide or live candidate pool. Do not replace this with vague wording
  such as "explore the area" or "walk around downtown". Only state hours,
  booking requirements or exact prices when a source returned them.
- Meals are recommendations too: when recommending breakfast, lunch, dinner
  or coffee, name one specific restaurant, café or food market from the search
  results. Explain the meal choice briefly only when supported by a source. If
  no named food venue is available, call it flexible meal time.
- Build a varied route across the requested days. Do not recommend the same
  venue twice anywhere in the itinerary. Before writing, gather a pool of
  distinct named venues large enough for the number of days, and group nearby
  venues on the same day rather than repeating a famous landmark.
- Structure the answer as one section per day.
- Keep it concise and practical, not flowery.
- End with a "מקורות" section that lists the unique source URLs returned by
  search_knowledge. Never invent or alter a source URL.
"""


class TripServiceUnavailable(RuntimeError):
    """The provider remains unavailable after bounded HTTP retries."""


class TripPlanningAgent:
    """
    עוטף client של Gemini + שני הכלים, וחושף plan_trip() כפעולה אחת.
    טוען את מודל ה-embeddings (Retriever) פעם אחת ב-__init__ - זה איטי
    (כמה שניות), לא רוצים לעשות את זה בכל קריאה ל-plan_trip.
    """

    def __init__(self, api_key: str | None = None, model: str = GEMINI_MODEL, retriever: Retriever | None = None,
                 venue_provider=None):
        resolved_key = api_key or GEMINI_API_KEY
        if not resolved_key:
            raise RuntimeError(
                "אין GEMINI_API_KEY - הגדר אותו ב-.env בשורש הפרויקט "
                "(ראו https://aistudio.google.com/apikey לקבלת מפתח חינמי)"
            )
        self.client = genai.Client(
            api_key=resolved_key,
            http_options=types.HttpOptions(
                timeout=60_000,
                retry_options=types.HttpRetryOptions(
                    attempts=3, initial_delay=2, max_delay=8,
                    http_status_codes=[503],
                ),
            ),
        )
        self.model = model
        self.models = tuple(dict.fromkeys((model, GEMINI_FALLBACK_MODEL)))
        self.active_model = model
        self.retriever = retriever or Retriever()
        if venue_provider is None:
            from app.location_lookup import candidate_pool_for_planning
            venue_provider = candidate_pool_for_planning
        self.venue_provider = venue_provider
        self.last_candidate_pool = ""

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
        return "\n\n".join(
            f"[{result['section']}] {result['text']}"
            + (f"\nSource: {result['source']}" if result.get("source") else "")
            for result in results
        )

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

        try:
            candidate_pool = self.venue_provider(city, days)
        except Exception:
            # The curated guide remains a valid evidence source if live OSM
            # candidate discovery is temporarily unavailable.
            candidate_pool = "No live venue candidates were available; use only named venues from the curated guide."
        self.last_candidate_pool = candidate_pool
        prompt = (
            f"Plan a {days}-day trip to {city}. "
            f"Total budget: ${budget_total_usd} USD (excluding flights and accommodation). "
            f"Traveler preferences: {preferences or 'none given - keep it well-rounded'}. "
            "For every attraction, recommend a concrete place with its proper name; do not use generic labels such as a market, a gallery or a museum. "
            "Here is a live, diverse pool of named OpenStreetMap candidates. Use it together with the curated guide, "
            "choose different venues across the days, and keep names in Hebrew transliteration in the final answer. "
            "Do not claim that a candidate is open or has a particular price unless search_knowledge supports it.\n"
            f"LIVE VENUE CANDIDATES:\n{candidate_pool}"
        )
        last_provider_error = None
        for model in self.models:
            chat = self.client.chats.create(
                model=model,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[self.search_knowledge, self.estimate_daily_budget],
                ),
            )
            try:
                response = chat.send_message(prompt)

                def has_foreign_text(text):
                    prose = re.sub(r"https?://[^\s<>]+", "", text or "")
                    return bool(re.search(r"[A-Za-zÀ-ž]", prose))

                if has_foreign_text(response.text):
                    response = chat.send_message(
                        "תקן את התשובה האחרונה לעברית בלבד. תעתק לעברית כל שם "
                        "של אתר, מסעדה או יישומון. הסר שמות לועזיים בסוגריים. "
                        "שמור על כל העובדות, הסכומים והקישורים ללא שינוי. "
                        "אל תקרא לכלים נוספים. החזר רק את המסלול המתוקן."
                    )
                if not response.text or has_foreign_text(response.text):
                    raise RuntimeError("The itinerary did not pass Hebrew output validation")
                self.active_model = model
                return response.text
            except errors.APIError as error:
                # A retired model must not turn a temporary quota issue into
                # a public 503. Try the configured fallback first.
                if error.code in {404, 429, 503} or model != self.model:
                    last_provider_error = error
                    continue
                raise
        raise TripServiceUnavailable(
            "שירות בניית המסלולים אינו זמין כרגע. "
            "אפשר לנסות שוב בעוד כמה דקות."
        ) from last_provider_error


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
