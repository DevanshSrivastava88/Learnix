"""Tests for nim_svc — NVIDIA NIM proof-of-concept provider.

All tests mock the OpenAI client so no real API key is needed.
"""
from unittest.mock import MagicMock, patch
import json
import pytest

import nim_svc


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_text_response(text: str):
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


def _make_json_response(payload) -> MagicMock:
    return _make_text_response(json.dumps(payload))


def _mock_client(response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


# ── _get_client ──────────────────────────────────────────────────────────────

def test_get_client_lazy_init():
    nim_svc._client = None
    with patch.dict("os.environ", {"NIM_API_KEY": "test-key"}), \
         patch("nim_svc.OpenAI") as MockOpenAI:
        MockOpenAI.return_value = MagicMock()
        c1 = nim_svc._get_client()
        c2 = nim_svc._get_client()
        assert c1 is c2
        MockOpenAI.assert_called_once()
    nim_svc._client = None


def test_get_client_uses_nim_base_url():
    nim_svc._client = None
    with patch.dict("os.environ", {"NIM_API_KEY": "test-key"}), \
         patch("nim_svc.OpenAI") as MockOpenAI:
        MockOpenAI.return_value = MagicMock()
        nim_svc._get_client()
        _, kwargs = MockOpenAI.call_args
        assert "integrate.api.nvidia.com" in kwargs.get("base_url", "")
    nim_svc._client = None


# ── _ask ─────────────────────────────────────────────────────────────────────

def test_ask_returns_stripped_text():
    client = _mock_client(_make_text_response("  hello world  "))
    with patch("nim_svc._get_client", return_value=client):
        result = nim_svc._ask("test prompt")
    assert result == "hello world"


def test_ask_passes_model_and_prompt():
    client = _mock_client(_make_text_response("ok"))
    with patch("nim_svc._get_client", return_value=client):
        nim_svc._ask("my prompt", max_tokens=512)
    call_kwargs = client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == nim_svc.MODEL
    assert call_kwargs["messages"][0]["content"] == "my prompt"
    assert call_kwargs["max_tokens"] == 512


# ── _ask_json ────────────────────────────────────────────────────────────────

def test_ask_json_requests_json_format():
    client = _mock_client(_make_json_response({"key": "val"}))
    with patch("nim_svc._get_client", return_value=client):
        nim_svc._ask_json("return json")
    call_kwargs = client.chat.completions.create.call_args[1]
    assert call_kwargs.get("response_format") == {"type": "json_object"}


def test_ask_json_parses_dict():
    payload = {"intent": "task"}
    client = _mock_client(_make_json_response(payload))
    with patch("nim_svc._get_client", return_value=client):
        result = nim_svc._ask_json("classify")
    assert result == payload


def test_ask_json_parses_list():
    payload = [{"question": "Q1", "expected_answer": "A1"}]
    client = _mock_client(_make_json_response(payload))
    with patch("nim_svc._get_client", return_value=client):
        result = nim_svc._ask_json("quiz")
    assert isinstance(result, list)
    assert result[0]["question"] == "Q1"


# ── teach_topic ──────────────────────────────────────────────────────────────

def test_teach_topic_returns_string():
    with patch("nim_svc._ask", return_value="Explanation here.") as mock_ask:
        result = nim_svc.teach_topic("Python generators")
    assert result == "Explanation here."
    mock_ask.assert_called_once()


def test_teach_topic_includes_notes_when_provided():
    with patch("nim_svc._ask", return_value="With notes.") as mock_ask:
        nim_svc.teach_topic("Closures", notes="A closure captures variables.")
    prompt = mock_ask.call_args[0][0]
    assert "A closure captures variables." in prompt


# ── generate_quiz ─────────────────────────────────────────────────────────────

def test_generate_quiz_returns_list_of_dicts():
    questions = [{"question": f"Q{i}", "expected_answer": f"A{i}"} for i in range(5)]
    with patch("nim_svc._ask_json", return_value=questions):
        result = nim_svc.generate_quiz("Python")
    assert len(result) == 5
    assert result[0]["question"] == "Q0"


def test_generate_quiz_truncates_to_five():
    questions = [{"question": f"Q{i}", "expected_answer": f"A{i}"} for i in range(8)]
    with patch("nim_svc._ask_json", return_value=questions):
        result = nim_svc.generate_quiz("Python")
    assert len(result) == 5


def test_generate_quiz_raises_on_non_list():
    with patch("nim_svc._ask_json", return_value={"error": "bad"}):
        with pytest.raises(ValueError, match="expected JSON array"):
            nim_svc.generate_quiz("Python")


# ── score_answer ──────────────────────────────────────────────────────────────

def test_score_answer_returns_dict_with_correct_and_explanation():
    payload = {"correct": True, "explanation": "Right concept."}
    with patch("nim_svc._ask_json", return_value=payload):
        result = nim_svc.score_answer("Q?", "Expected.", "User answer.")
    assert result["correct"] is True
    assert "explanation" in result


# ── classify_intent ───────────────────────────────────────────────────────────

def test_classify_intent_returns_intent_string():
    with patch("nim_svc._ask_json", return_value={"intent": "task"}):
        result = nim_svc.classify_intent("remind me to drink water every day")
    assert result == "task"


def test_classify_intent_defaults_to_chat_on_missing_key():
    with patch("nim_svc._ask_json", return_value={}):
        result = nim_svc.classify_intent("hello")
    assert result == "chat"


def test_classify_intent_includes_context_in_prompt():
    captured = {}
    def fake_ask_json(prompt):
        captured["prompt"] = prompt
        return {"intent": "chat"}
    with patch("nim_svc._ask_json", side_effect=fake_ask_json):
        nim_svc.classify_intent("ok", context="User said: remind me later")
    assert "User said: remind me later" in captured["prompt"]


# ── parse_task ────────────────────────────────────────────────────────────────

def test_parse_task_returns_dict():
    payload = {"type": "habit", "title": "Morning run", "recurrence_days": 1,
               "delay_minutes": None, "description": "", "clarify": ""}
    with patch("nim_svc._ask_json", return_value=payload):
        result = nim_svc.parse_task("remind me to run every morning")
    assert result["type"] == "habit"
    assert result["title"] == "Morning run"


# ── breakdown helpers ─────────────────────────────────────────────────────────

def test_breakdown_task_returns_list_of_strings():
    steps = ["Warmup", "Push-ups", "Cool down"]
    with patch("nim_svc._ask_json", return_value=steps):
        result = nim_svc.breakdown_task("Morning workout")
    assert result == steps


def test_breakdown_task_raises_on_non_list():
    with patch("nim_svc._ask_json", return_value={"steps": []}):
        with pytest.raises(ValueError, match="expected JSON array"):
            nim_svc.breakdown_task("workout")


def test_breakdown_study_goal_returns_list():
    topics = ["Variables", "Control Flow", "Functions"]
    with patch("nim_svc._ask_json", return_value=topics):
        result = nim_svc.breakdown_study_goal("Learn Python")
    assert result == topics


# ── extract helpers ───────────────────────────────────────────────────────────

def test_extract_task_name_returns_string():
    with patch("nim_svc._ask_json", return_value={"task_name": "workout"}):
        assert nim_svc.extract_task_name_from_message("done with workout") == "workout"


def test_extract_topic_name_returns_string():
    with patch("nim_svc._ask_json", return_value={"topic_name": "OOP Basics"}):
        assert nim_svc.extract_topic_name("study OOP Basics") == "OOP Basics"


def test_extract_goal_name_returns_string():
    with patch("nim_svc._ask_json", return_value={"goal_name": "Python"}):
        assert nim_svc.extract_goal_name_from_message("I want to learn Python") == "Python"


def test_extract_reschedule_info_returns_dict():
    with patch("nim_svc._ask_json", return_value={"task_name": "workout", "time": "06:00"}):
        result = nim_svc.extract_reschedule_info("remind me about workout at 6am")
    assert result["task_name"] == "workout"
    assert result["time"] == "06:00"


def test_extract_set_time_info_returns_dict():
    with patch("nim_svc._ask_json", return_value={"time_type": "study", "time_value": "21:00"}):
        result = nim_svc.extract_set_time_info("I want to study at 9pm")
    assert result["time_type"] == "study"
    assert result["time_value"] == "21:00"


# ── daily_summary ─────────────────────────────────────────────────────────────

def test_daily_summary_returns_string():
    with patch("nim_svc._ask", return_value="Good morning! 🚀"):
        result = nim_svc.daily_summary({"streak": 3, "goal": "Python"})
    assert result == "Good morning! 🚀"


# ── transcribe_voice ──────────────────────────────────────────────────────────

def test_transcribe_voice_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        nim_svc.transcribe_voice("/tmp/audio.ogg")
