"""
בונה בסיס ידע (RAG) עמוק לכמה ערים נבחרות (לא כל 18 - זה יקר/מוגזם לשלב הזה),
לשימוש עתידי ב-Trip Planning Agent (שלב 3 בתכנון - עדיין TODO).

מקור התוכן: Wikivoyage (https://en.wikivoyage.org) - מדריכי טיולים בקוד פתוח
(רישיון CC BY-SA), עם API רשמי וחינמי דרך MediaWiki - בניגוד ל-Numbeo,
Wikivoyage *מיועד* לגישה תכנותית כזו, אין כאן שאלת ToS.
קרדיט (כנדרש ב-CC BY-SA): התוכן לקוח מ-Wikivoyage, https://en.wikivoyage.org
(ראו קישור ספציפי לכל עיר ב-ATTRIBUTION_URLS).

איך זה עובד:
1. שולף את הערך המלא (טקסט רגיל, לא wikitext) מ-Wikivoyage ל-CITIES.
2. מפרק לצ'אנקים לפי סקשנים (== Understand ==, == See ==, == Eat == וכו'),
   ומפצל צ'אנקים ארוכים מדי (לפי פרגרפים, ואז לפי משפטים אם צריך).
3. מחשב embedding מקומי לכל צ'אנק (sentence-transformers - בלי API/מפתח).
4. שומר ל-rag/knowledge_base/<city>_chunks.json (הטקסטים + מטא-דאטה)
   ו-<city>_embeddings.npy (מטריצת embeddings, באותו סדר).

שימוש:
    python rag/build_knowledge_base.py
"""

import json
import os
import re
import sys
import time

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ערים נבחרות ל-RAG - לא כל 18 מ-config.CITIES. אלה "case studies" עמוקים,
# לא עוד ציר/שדה על כל עיר. אם תרצו להוסיף עיר, פשוט הוסיפו לרשימה כאן.
RAG_CITIES = ["Paris", "Prague", "Vienna"]

WIKIVOYAGE_API_URL = "https://en.wikivoyage.org/w/api.php"
WIKIVOYAGE_HEADERS = {"User-Agent": "TravelDNA-course-project/1.0 (RAG knowledge base build)"}

# all-mpnet-base-v2 ולא all-MiniLM-L6-v2 (קטן/מהיר יותר) - בדקנו את שניהם
# על השאילתה "how to get around by public transport" בפריז: MiniLM שם את
# הסקשן "By public transport" עצמו רק במקום ~15 (מתחת ל-"By car"!), בעוד
# ש-mpnet שם אותו ב-top 7 והעלה גם By bus/By M?tro/By tram - טעות איכות
# ממשית, לא רק הבדל קוסמטי. mpnet יותר גדול (~420MB) ואיטי יותר, אבל עדיין
# מקומי/חינמי/בלי מפתח - אותה קטגוריה, פשוט מודל טוב יותר בתוכה.
EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"

MAX_CHUNK_CHARS = 500  # צ'אנק ארוך מדי נחתך/מקוצץ ע"י המודל בזמן embedding
MIN_CHUNK_CHARS = 40   # צ'אנקים קטנים מזה הם כותרות ניווט בלי תוכן ממשי

KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")

# קישור ספציפי לכל עיר, לצורך קרדיט מדויק (נדרש ב-CC BY-SA)
ATTRIBUTION_URLS = {city: f"https://en.wikivoyage.org/wiki/{city}" for city in RAG_CITIES}


def fetch_wikivoyage_article(title: str) -> str:
    """שולף את הטקסט המלא (בלי wiki-markup) של ערך Wikivoyage."""
    resp = requests.get(
        WIKIVOYAGE_API_URL,
        params={"action": "query", "titles": title, "prop": "extracts", "explaintext": 1, "format": "json"},
        headers=WIKIVOYAGE_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    if "missing" in page:
        raise ValueError(f"לא נמצא ערך Wikivoyage בשם '{title}'")
    return page.get("extract", "")


def _split_long_text(text: str, max_chars: int) -> list[str]:
    """מפצל טקסט ארוך מדי לחתיכות קטנות ממנו, לפי משפטים (לא באמצע משפט)."""
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, buf = [], ""
    for sentence in sentences:
        if buf and len(buf) + len(sentence) > max_chars:
            pieces.append(buf)
            buf = sentence
        else:
            buf = (buf + " " + sentence) if buf else sentence
    if buf:
        pieces.append(buf)
    return pieces


def chunk_article(text: str, max_chunk_chars: int = MAX_CHUNK_CHARS, min_chunk_chars: int = MIN_CHUNK_CHARS) -> list[dict]:
    """
    מפרק ערך שלם ל-{"section": ..., "text": ...} לפי כותרות == Section ==
    (בכל עומק קינון - לא מבחינים בין == ל-====, זה לא משנה לצורך retrieval),
    ובתוך כל סקשן - לפי פרגרפים, ומפצל פרגרף בודד שעדיין ארוך מדי לפי משפטים.
    מסנן החוצה צ'אנקים קצרים מדי (כותרות ניווט בלי תוכן).
    """
    parts = re.split(r"\n=+\s*(.+?)\s*=+\n", text)
    sections = [("Overview", parts[0])] + list(zip(parts[1::2], parts[2::2]))

    chunks = []
    for title, body in sections:
        body = body.strip()
        if not body:
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]

        buf = ""
        for paragraph in paragraphs:
            if buf and len(buf) + len(paragraph) > max_chunk_chars:
                if len(buf) >= min_chunk_chars:
                    chunks.append({"section": title, "text": buf})
                buf = paragraph
            else:
                buf = (buf + " " + paragraph) if buf else paragraph
        if len(buf) >= min_chunk_chars:
            chunks.append({"section": title, "text": buf})

    # עוד מעבר - לפצל כל צ'אנק שעדיין ארוך מדי (פרגרף בודד שגדול מ-max לבדו)
    final_chunks = []
    for chunk in chunks:
        for piece in _split_long_text(chunk["text"], max_chunk_chars):
            if len(piece) >= min_chunk_chars:
                final_chunks.append({"section": chunk["section"], "text": piece})
    return final_chunks


def build_city_knowledge_base(city: str, model: SentenceTransformer) -> int:
    """בונה ושומר את בסיס הידע לעיר אחת. מחזיר את מספר הצ'אנקים שנוצרו."""
    print(f"שולף ערך Wikivoyage עבור {city}...")
    article_text = fetch_wikivoyage_article(city)
    time.sleep(1)  # לא להציף את ה-API של Wikimedia בבקשות עוקבות

    chunks = chunk_article(article_text)
    print(f"  {len(chunks)} צ'אנקים, מחשב embeddings...")

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)

    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    chunks_with_meta = [
        {"city": city, "section": c["section"], "text": c["text"], "source": ATTRIBUTION_URLS[city]}
        for c in chunks
    ]
    with open(os.path.join(KNOWLEDGE_BASE_DIR, f"{city}_chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks_with_meta, f, ensure_ascii=False, indent=2)
    np.save(os.path.join(KNOWLEDGE_BASE_DIR, f"{city}_embeddings.npy"), embeddings)

    return len(chunks)


def main():
    print(f"טוען מודל embeddings ({EMBEDDING_MODEL_NAME}, מקומי - הורדה חד-פעמית אם לא קיים)...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    total = 0
    for city in RAG_CITIES:
        total += build_city_knowledge_base(city, model)

    print(f"\nהושלם! {total} צ'אנקים סה\"כ עבור {len(RAG_CITIES)} ערים, נשמרו ב-{KNOWLEDGE_BASE_DIR}")


if __name__ == "__main__":
    main()
