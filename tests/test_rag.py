"""
בדיקות יחידה ל-rag/build_knowledge_base.py ו-rag/retriever.py.

לא טוענות את מודל ה-embeddings האמיתי בכלל (הוא כבד - ~420MB, ולא צריך
רשת/מודל בשביל לבדוק לוגיקה) - מדמות (mock) את SentenceTransformer,
ובודקות רק: פיצול לצ'אנקים, ומיון לפי דמיון קוסינוס על embeddings מוכרים.
"""

import json
import os
import sys
from unittest import mock

import numpy as np
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)

from rag.build_knowledge_base import chunk_article, _split_long_text
from rag import retriever as retriever_module


# ---- chunk_article / _split_long_text - פונקציות טהורות, בלי מודל/רשת ----

def test_chunk_article_splits_by_section_headers():
    text = (
        "Intro paragraph text here that is long enough to count as a real chunk.\n"
        "== Understand ==\n"
        "This city is great for tourists and has many attractions worth seeing here.\n"
        "== Eat ==\n"
        "Try the local food, it is delicious and famous worldwide for its flavor profile."
    )
    chunks = chunk_article(text, max_chunk_chars=1000, min_chunk_chars=10)
    sections = [c["section"] for c in chunks]
    assert "Overview" in sections
    assert "Understand" in sections
    assert "Eat" in sections


def test_chunk_article_filters_out_short_navigation_headers():
    text = (
        "Real content paragraph that is long enough to pass the minimum length threshold.\n"
        "== Get in ==\n"
        "x\n"
        "== See ==\n"
        "Another long enough paragraph describing what to see in this wonderful city."
    )
    chunks = chunk_article(text, min_chunk_chars=20)
    sections = [c["section"] for c in chunks]
    assert "Get in" not in sections  # "x" קצר מדי - צריך להיפסל
    assert "See" in sections


def test_chunk_article_splits_long_section_into_multiple_chunks():
    long_paragraph = "This is a sentence about the city. " * 40  # ~1400 chars
    text = f"Intro.\n== Understand ==\n{long_paragraph}"
    chunks = chunk_article(text, max_chunk_chars=300, min_chunk_chars=10)
    understand_chunks = [c for c in chunks if c["section"] == "Understand"]
    assert len(understand_chunks) > 1
    assert all(len(c["text"]) <= 320 for c in understand_chunks)  # קצת סלאק למשפט אחרון


def test_split_long_text_returns_single_piece_if_already_short():
    text = "short text"
    assert _split_long_text(text, max_chars=100) == [text]


def test_split_long_text_does_not_split_mid_sentence():
    text = "First sentence here. Second sentence here. Third sentence here. Fourth one too."
    pieces = _split_long_text(text, max_chars=30)
    assert len(pieces) > 1
    # כל הטקסט המקורי נשמר (לא אבד תוכן בפיצול)
    assert "".join(pieces).replace("  ", " ") == text or " ".join(
        p.strip() for p in pieces
    ) == text


# ---- Retriever - עם SentenceTransformer מדומה (mock), embeddings ידועים ----

def _write_fake_knowledge_base(kb_dir, city, chunks, embeddings):
    with open(os.path.join(kb_dir, f"{city}_chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    np.save(os.path.join(kb_dir, f"{city}_embeddings.npy"), np.array(embeddings))


def test_retrieve_ranks_by_cosine_similarity(tmp_path, monkeypatch):
    chunks = [
        {"city": "TestCity", "section": "A", "text": "chunk about cats", "source": "x"},
        {"city": "TestCity", "section": "B", "text": "chunk about dogs", "source": "x"},
        {"city": "TestCity", "section": "C", "text": "chunk about birds", "source": "x"},
    ]
    embeddings = [
        [1.0, 0.0],   # A - זהה לוקטור השאילתה
        [0.0, 1.0],   # B - אורתוגונלי (לא קשור)
        [-1.0, 0.0],  # C - הפוך (הכי לא רלוונטי)
    ]
    _write_fake_knowledge_base(tmp_path, "TestCity", chunks, embeddings)
    monkeypatch.setattr(retriever_module, "_KNOWLEDGE_BASE_DIR", str(tmp_path))

    fake_model = mock.Mock()
    fake_model.encode.return_value = [np.array([1.0, 0.0])]

    with mock.patch.object(retriever_module, "SentenceTransformer", return_value=fake_model):
        r = retriever_module.Retriever()
        results = r.retrieve("anything", "TestCity", top_k=3)

    assert [res["section"] for res in results] == ["A", "B", "C"]
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[1]["score"] == pytest.approx(0.0, abs=1e-6)
    assert results[2]["score"] == pytest.approx(-1.0)


def test_retrieve_top_k_larger_than_available_does_not_crash(tmp_path, monkeypatch):
    chunks = [{"city": "TestCity", "section": "A", "text": "only chunk", "source": "x"}]
    _write_fake_knowledge_base(tmp_path, "TestCity", chunks, [[1.0, 0.0]])
    monkeypatch.setattr(retriever_module, "_KNOWLEDGE_BASE_DIR", str(tmp_path))

    fake_model = mock.Mock()
    fake_model.encode.return_value = [np.array([1.0, 0.0])]

    with mock.patch.object(retriever_module, "SentenceTransformer", return_value=fake_model):
        r = retriever_module.Retriever()
        results = r.retrieve("q", "TestCity", top_k=10)

    assert len(results) == 1


def test_retrieve_missing_city_raises_filenotfound(tmp_path, monkeypatch):
    monkeypatch.setattr(retriever_module, "_KNOWLEDGE_BASE_DIR", str(tmp_path))
    fake_model = mock.Mock()

    with mock.patch.object(retriever_module, "SentenceTransformer", return_value=fake_model):
        r = retriever_module.Retriever()
        with pytest.raises(FileNotFoundError):
            r.retrieve("q", "NoSuchCity")


def test_available_cities_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(retriever_module, "_KNOWLEDGE_BASE_DIR", str(tmp_path / "does_not_exist"))
    assert retriever_module.available_cities() == []


def test_available_cities_lists_the_real_built_knowledge_base():
    # בדיקת אינטגרציה קלה - שהבסיס שבנינו בפועל (Paris/Prague/Vienna) קיים
    # בדיסק. לא טוענת שום מודל, רק בודקת קבצים.
    cities = retriever_module.available_cities()
    assert {"Paris", "Prague", "Vienna"}.issubset(set(cities))
