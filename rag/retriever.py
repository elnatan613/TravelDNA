"""
חיפוש סמנטי (retrieval) בבסיס הידע שנבנה ע"י build_knowledge_base.py.
לא בונה שום דבר - רק טוען את הצ'אנקים/embeddings הקיימים וממיין לפי דמיון
(cosine similarity) לשאלה. מיועד לשימוש ע"י Trip Planning Agent (TODO,
עדיין לא קיים) ברגע שיבנה.

שימוש עצמאי:
    python rag/retriever.py "מה יש לראות בפריז?" Paris
"""

import json
import os
import sys

import numpy as np
from sentence_transformers import SentenceTransformer

_KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
# חייב להיות אותו מודל שנבנה איתו בסיס הידע (ראו הערה ב-build_knowledge_base.py
# על למה mpnet ולא MiniLM - הבדל איכות ממשי, לא רק קוסמטי)
_EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"


def available_cities() -> list[str]:
    """הערים שיש להן בסיס ידע בפועל (נבנה קבצי chunks+embeddings)."""
    if not os.path.isdir(_KNOWLEDGE_BASE_DIR):
        return []
    return sorted(
        fname[: -len("_chunks.json")]
        for fname in os.listdir(_KNOWLEDGE_BASE_DIR)
        if fname.endswith("_chunks.json")
    )


class Retriever:
    """
    טוען מודל embeddings פעם אחת, ומאפשר לחפש (retrieve) בכל עיר שיש לה
    בסיס ידע. שומר בזיכרון (cache) כל עיר שנטענה, כדי לא לקרוא מהדיסק בכל
    שאילתה.
    """

    def __init__(self, model_name: str = _EMBEDDING_MODEL_NAME):
        self.model = SentenceTransformer(model_name)
        self._city_cache: dict[str, tuple[list[dict], np.ndarray]] = {}

    def _load_city(self, city: str) -> tuple[list[dict], np.ndarray]:
        if city in self._city_cache:
            return self._city_cache[city]

        chunks_path = os.path.join(_KNOWLEDGE_BASE_DIR, f"{city}_chunks.json")
        embeddings_path = os.path.join(_KNOWLEDGE_BASE_DIR, f"{city}_embeddings.npy")
        if not os.path.exists(chunks_path) or not os.path.exists(embeddings_path):
            raise FileNotFoundError(
                f"אין בסיס ידע (RAG) לעיר '{city}'. ערים קיימות: {available_cities()} "
                "(הרץ python rag/build_knowledge_base.py כדי לבנות, ותתאם עם config.RAG_CITIES-style list)"
            )

        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)
        embeddings = np.load(embeddings_path)

        self._city_cache[city] = (chunks, embeddings)
        return chunks, embeddings

    def retrieve(self, query: str, city: str, top_k: int = 5) -> list[dict]:
        """
        מחזיר את top_k הצ'אנקים הרלוונטיים ביותר לשאלה, ממוינים מהגבוה
        לנמוך לפי דמיון קוסינוס. כל תוצאה: {"city", "section", "text",
        "source", "score"}.
        """
        chunks, embeddings = self._load_city(city)
        query_embedding = self.model.encode([query])[0]

        # cosine similarity = מכפלה פנימית מנורמלת (embeddings כבר בגודל קבוע
        # מהמודל, לא מנורמלים ל-1 בהכרח - מנרמלים כאן במפורש כדי להיות בטוחים)
        norms = np.linalg.norm(embeddings, axis=1)
        query_norm = np.linalg.norm(query_embedding)
        similarities = (embeddings @ query_embedding) / (norms * query_norm + 1e-10)

        top_k = min(top_k, len(chunks))
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [{**chunks[i], "score": round(float(similarities[i]), 3)} for i in top_indices]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("שימוש: python rag/retriever.py \"<שאלה>\" <עיר>")
        print(f"ערים זמינות: {available_cities()}")
        sys.exit(1)

    query, city = sys.argv[1], sys.argv[2]
    retriever = Retriever()
    for result in retriever.retrieve(query, city):
        print(f"[{result['score']}] ({result['section']}) {result['text'][:150]}...")
