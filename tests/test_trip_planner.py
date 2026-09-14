"""
בדיקות יחידה ל-agent/trip_planner.py.

לא פוגעות ברשת/API בכלל - מדמות (mock) גם את genai.Client (Gemini) וגם את
ה-Retriever (כדי לא לטעון את מודל ה-embeddings הכבד). בודקות רק: התנהגות
הכלים (search_knowledge/estimate_daily_budget) והשומרים (guards) של
plan_trip - לא את התוכן שה-LLM בעצמו מייצר (זה לא דטרמיניסטי, אין מה לבדוק).
"""

import os
import sys
from unittest import mock

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_PROJECT_ROOT)
sys.path.append(os.path.join(_PROJECT_ROOT, "scripts"))

with mock.patch("google.genai.Client"):
    from agent.trip_planner import TripPlanningAgent


def _make_agent(retriever=None):
    with mock.patch("agent.trip_planner.genai.Client"):
        return TripPlanningAgent(api_key="fake-key-for-tests", retriever=retriever or mock.Mock())


def test_init_raises_without_api_key():
    with mock.patch("agent.trip_planner.GEMINI_API_KEY", ""):
        with mock.patch("agent.trip_planner.genai.Client"):
            with pytest.raises(RuntimeError):
                TripPlanningAgent(api_key="", retriever=mock.Mock())


def test_search_knowledge_formats_results():
    fake_retriever = mock.Mock()
    fake_retriever.retrieve.return_value = [
        {
            "section": "See",
            "text": "The Louvre is a great museum.",
            "source": "https://en.wikivoyage.org/wiki/Paris",
            "score": 0.8,
        },
        {
            "section": "Eat",
            "text": "Try the local bistros.",
            "source": "https://en.wikivoyage.org/wiki/Paris",
            "score": 0.6,
        },
    ]
    agent = _make_agent(retriever=fake_retriever)

    result = agent.search_knowledge("Paris", "museums")

    assert "[See] The Louvre is a great museum." in result
    assert "[Eat] Try the local bistros." in result
    assert "Source: https://en.wikivoyage.org/wiki/Paris" in result
    fake_retriever.retrieve.assert_called_once_with("museums", "Paris", top_k=4)


def test_search_knowledge_missing_city_returns_helpful_message_not_crash():
    fake_retriever = mock.Mock()
    fake_retriever.retrieve.side_effect = FileNotFoundError("no such city")
    agent = _make_agent(retriever=fake_retriever)

    result = agent.search_knowledge("Atlantis", "anything")
    assert "Atlantis" in result
    assert "Available cities" in result


def test_search_knowledge_no_results_returns_message():
    fake_retriever = mock.Mock()
    fake_retriever.retrieve.return_value = []
    agent = _make_agent(retriever=fake_retriever)

    result = agent.search_knowledge("Paris", "something obscure")
    assert "No relevant information" in result


def test_estimate_daily_budget_known_city():
    agent = _make_agent()
    result = agent.estimate_daily_budget("Paris")
    assert "Paris" in result
    assert "USD" in result


def test_estimate_daily_budget_unknown_city_returns_message_not_crash():
    agent = _make_agent()
    result = agent.estimate_daily_budget("Atlantis")
    assert "No cost-of-living data" in result
    assert "Atlantis" in result


def test_plan_trip_unsupported_city_short_circuits_without_calling_llm():
    fake_client = mock.Mock()
    agent = _make_agent()
    agent.client = fake_client  # אחרי הבנייה - מחליף ב-mock שנוכל לבדוק שלא נקרא

    result = agent.plan_trip("Atlantis", days=3, budget_total_usd=500)

    assert "Atlantis" in result
    fake_client.chats.create.assert_not_called()  # לא היה אמור לפנות ל-LLM בכלל


def test_plan_trip_supported_city_calls_llm_with_tools():
    fake_client = mock.Mock()
    fake_chat = mock.Mock()
    fake_chat.send_message.return_value.text = "מסלול לדוגמה"
    fake_client.chats.create.return_value = fake_chat

    agent = _make_agent()
    agent.client = fake_client

    with mock.patch("agent.trip_planner.available_cities", return_value=["Paris", "Prague", "Vienna"]):
        result = agent.plan_trip("Paris", days=2, budget_total_usd=300, preferences="loves food")

    assert result == "מסלול לדוגמה"
    create_kwargs = fake_client.chats.create.call_args.kwargs
    tool_names = {tool.__name__ for tool in create_kwargs["config"].tools}
    assert tool_names == {"search_knowledge", "estimate_daily_budget"}
    system_instruction = create_kwargs["config"].system_instruction
    assert "Hebrew" in system_instruction
    assert "מקורות" in system_instruction
    sent_prompt = fake_chat.send_message.call_args.args[0]
    assert "Paris" in sent_prompt and "2-day" in sent_prompt and "300" in sent_prompt


def test_client_retries_overload_at_http_level():
    with mock.patch("agent.trip_planner.genai.Client") as client:
        TripPlanningAgent(api_key="test", retriever=mock.Mock())
    options = client.call_args.kwargs["http_options"]
    assert options.retry_options.attempts == 3
    assert options.retry_options.http_status_codes == [503]
    assert options.timeout == 60_000


def test_foreign_names_are_rewritten_but_source_urls_are_allowed():
    agent = _make_agent()
    chat = agent.client.chats.create.return_value
    chat.send_message.side_effect = [
        mock.Mock(text="בקרו ב-Porto"),
        mock.Mock(text="בקרו בפורטו\nhttps://en.wikivoyage.org/wiki/Porto"),
    ]
    with mock.patch("agent.trip_planner.available_cities", return_value=["Porto"]):
        result = agent.plan_trip("Porto", 1, 150)
    assert "בקרו בפורטו" in result
    assert chat.send_message.call_count == 2


@pytest.mark.parametrize("code", [429, 503, 400, 403])
def test_provider_errors_are_classified(code):
    from google.genai.errors import APIError
    from agent.trip_planner import TripServiceUnavailable

    agent = _make_agent()
    error = APIError(code, {"error": {"message": "provider details", "code": code}})
    agent.client.chats.create.return_value.send_message.side_effect = error
    with mock.patch("agent.trip_planner.available_cities", return_value=["Paris"]):
        with pytest.raises(TripServiceUnavailable if code in {429, 503} else APIError) as caught:
            agent.plan_trip("Paris", 3, 500)
    if code in {429, 503}:
        assert "provider details" not in str(caught.value)
        assert "אינו זמין" in str(caught.value)
    else:
        assert caught.value is error
