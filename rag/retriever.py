"""
חיפוש סמנטי (retrieval) בבסיס הידע שנבנה ע"י build_knowledge_base.py.
לא בונה שום דבר - רק טוען את הצ'אנקים/embeddings הקיימים וממיין לפי דמיון
(cosine similarity) לשאלה. מיועד לשימוש ע"י Trip Planning Agent.

שימוש עצמאי:
    python rag/retriever.py "מה יש לראות בפריז?" Paris
"""

import json
import os
import sys
import re

# The full embedding stack is deliberately optional. Railway's starter
# container has 1 GB RAM, while loading PyTorch plus all-mpnet-base-v2 exceeds
# that limit. Local development can keep using semantic retrieval; production
# uses the small lexical retriever below.
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
except ImportError:  # Production image does not install the heavy stack.
    np = None
    SentenceTransformer = None

_KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
# חייב להיות אותו מודל שנבנה איתו בסיס הידע (ראו הערה ב-build_knowledge_base.py
# על למה mpnet ולא MiniLM - הבדל איכות ממשי, לא רק קוסמטי)
_EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"


def available_cities() -> list[str]:
    """הערים שיש להן בסיס ידע בפועל (נבנה קבצי chunks+embeddings)."""
    if not os.path.isdir(_KNOWLEDGE_BASE_DIR):
        return []
    chunk_cities = {
        fname[: -len("_chunks.json")]
        for fname in os.listdir(_KNOWLEDGE_BASE_DIR)
        if fname.endswith("_chunks.json")
    }
    embedding_cities = {
        fname[: -len("_embeddings.npy")]
        for fname in os.listdir(_KNOWLEDGE_BASE_DIR)
        if fname.endswith("_embeddings.npy")
    }
    return sorted(chunk_cities & embedding_cities)


class Retriever:
    """
    טוען מודל embeddings פעם אחת, ומאפשר לחפש (retrieve) בכל עיר שיש לה
    בסיס ידע. שומר בזיכרון (cache) כל עיר שנטענה, כדי לא לקרוא מהדיסק בכל
    שאילתה.
    """

    def __init__(self, model_name: str = _EMBEDDING_MODEL_NAME, mode: str | None = None):
        self.mode = (mode or os.environ.get("TRAVELDNA_RAG_MODE", "semantic")).lower()
        if self.mode not in {"semantic", "lexical"}:
            raise ValueError("TRAVELDNA_RAG_MODE חייב להיות semantic או lexical")
        if self.mode == "semantic":
            if SentenceTransformer is None:
                raise RuntimeError(
                    "חיפוש סמנטי דורש sentence-transformers. "
                    "בפרודקשן הגדר TRAVELDNA_RAG_MODE=lexical."
                )
            self.model = SentenceTransformer(model_name)
        else:
            self.model = None
        self._city_cache: dict[str, tuple[list[dict], object | None]] = {}

    def _load_city(self, city: str) -> tuple[list[dict], object | None]:
        if city in self._city_cache:
            return self._city_cache[city]

        chunks_path = os.path.join(_KNOWLEDGE_BASE_DIR, f"{city}_chunks.json")
        embeddings_path = os.path.join(_KNOWLEDGE_BASE_DIR, f"{city}_embeddings.npy")
        if not os.path.exists(chunks_path) or not os.path.exists(embeddings_path):
            raise FileNotFoundError(
                f"אין בסיס ידע (RAG) לעיר '{city}'. ערים קיימות: {available_cities()} "
                "(הרץ python rag/build_knowledge_base.py כדי לבנות לפי config.CITIES)"
            )

        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)
        embeddings = np.load(embeddings_path) if self.mode == "semantic" else None

        self._city_cache[city] = (chunks, embeddings)
        return chunks, embeddings

    def retrieve(self, query: str, city: str, top_k: int = 5) -> list[dict]:
        """
        מחזיר את top_k הצ'אנקים הרלוונטיים ביותר לשאלה, ממוינים מהגבוה
        לנמוך לפי דמיון קוסינוס. כל תוצאה: {"city", "section", "text",
        "source", "score"}.
        """
        chunks, embeddings = self._load_city(city)
        if self.mode == "lexical":
            return self._lexical_retrieve(query, chunks, top_k)

        query_embedding = self.model.encode([query])[0]

        # cosine similarity = מכפלה פנימית מנורמלת (embeddings כבר בגודל קבוע
        # מהמודל, לא מנורמלים ל-1 בהכרח - מנרמלים כאן במפורש כדי להיות בטוחים)
        norms = np.linalg.norm(embeddings, axis=1)
        query_norm = np.linalg.norm(query_embedding)
        similarities = (embeddings @ query_embedding) / (norms * query_norm + 1e-10)

        top_k = min(top_k, len(chunks))
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [{**chunks[i], "score": round(float(similarities[i]), 3)} for i in top_indices]

    @staticmethod
    def _lexical_retrieve(query: str, chunks: list[dict], top_k: int) -> list[dict]:
        """Rank guide snippets by matching useful English query words.

        The guide corpus and the agent tool prompts are English. This keeps
        curated source material available in low-memory deployments while
        avoiding model downloads during a visitor's request.
        """
        tokens = {
            token for token in re.findall(r"[a-z0-9]{3,}", query.lower())
            if token not in {"about", "best", "city", "find", "from", "have", "into", "more", "that", "the", "this", "what", "with"}
        }
        scored = []
        for index, chunk in enumerate(chunks):
            haystack = f"{chunk.get('section', '')} {chunk.get('text', '')}".lower()
            hits = sum(token in haystack for token in tokens)
            # Keep guide order stable when there are no matches, so the
            # generator still gets an evidence-backed city overview.
            scored.append((hits, -index, chunk))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [
            {**chunk, "score": round(hits / max(len(tokens), 1), 3)}
            for hits, _, chunk in scored[:min(top_k, len(chunks))]
        ]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("שימוש: python rag/retriever.py \"<שאלה>\" <עיר>")
        print(f"ערים זמינות: {available_cities()}")
        sys.exit(1)

    query, city = sys.argv[1], sys.argv[2]
    retriever = Retriever()
    for result in retriever.retrieve(query, city):
        print(f"[{result['score']}] ({result['section']}) {result['text'][:150]}...")
