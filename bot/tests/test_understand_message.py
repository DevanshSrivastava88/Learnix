"""understand_message — routing and multi-task extraction."""
import json
from unittest.mock import MagicMock, patch

import claude_svc


def _resp(content):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    return r


def _understand(llm_json: dict):
    payload = json.dumps(llm_json)
    with patch.object(claude_svc, "_get_client") as gc, \
         patch.object(claude_svc, "_with_retry", side_effect=lambda fn, **kw: fn()):
        gc.return_value.chat.completions.create.return_value = _resp(payload)
        return claude_svc.understand_message("add call shreysh in 1h and mum in 2h")


def test_single_task_returns_empty_extra_tasks():
    result = _understand({
        "intent": "task",
        "task": {"type": "reminder", "title": "Call Shreysh", "description": "",
                 "time_minutes": 60, "time_hhmm": None, "day_offset": None,
                 "recurrence_days": 1, "clarify": ""},
        "extra_tasks": [],
        "task_ref": "",
    })
    assert result["intent"] == "task"
    assert result["extra_tasks"] == []
    assert result["task"]["title"] == "Call Shreysh"


def test_multi_task_extra_tasks_extracted():
    result = _understand({
        "intent": "task",
        "task": {"type": "reminder", "title": "Call Shreysh", "description": "",
                 "time_minutes": 60, "time_hhmm": None, "day_offset": None,
                 "recurrence_days": 1, "clarify": ""},
        "extra_tasks": [
            {"type": "reminder", "title": "Call Mum", "description": "",
             "time_minutes": 120, "time_hhmm": None, "day_offset": None,
             "recurrence_days": 1, "clarify": ""},
        ],
        "task_ref": "",
    })
    assert result["intent"] == "task"
    assert len(result["extra_tasks"]) == 1
    assert result["extra_tasks"][0]["title"] == "Call Mum"
    assert result["extra_tasks"][0]["time_minutes"] == 120


def test_extra_tasks_without_title_are_filtered():
    result = _understand({
        "intent": "task",
        "task": {"type": "reminder", "title": "Call Shreysh", "description": "",
                 "time_minutes": 60, "time_hhmm": None, "day_offset": None,
                 "recurrence_days": 1, "clarify": ""},
        "extra_tasks": [
            {"type": "reminder", "title": "", "description": ""},  # no title — filtered
            {"type": "reminder", "title": "Call Mum", "description": "",
             "time_minutes": 120, "time_hhmm": None, "day_offset": None,
             "recurrence_days": 1, "clarify": ""},
        ],
        "task_ref": "",
    })
    assert len(result["extra_tasks"]) == 1
    assert result["extra_tasks"][0]["title"] == "Call Mum"


def test_non_list_extra_tasks_returns_empty():
    result = _understand({
        "intent": "task",
        "task": {"type": "reminder", "title": "Workout", "description": "",
                 "time_minutes": None, "time_hhmm": None, "day_offset": None,
                 "recurrence_days": 1, "clarify": ""},
        "extra_tasks": None,  # LLM returned null instead of []
        "task_ref": "",
    })
    assert result["extra_tasks"] == []


def test_understand_uses_400_max_tokens():
    """Ensure max_tokens is 400 — enough for multi-task JSON responses."""
    with patch.object(claude_svc, "_get_client") as gc, \
         patch.object(claude_svc, "_with_retry", side_effect=lambda fn, **kw: fn()):
        gc.return_value.chat.completions.create.return_value = _resp(
            '{"intent":"chat","task":null,"extra_tasks":[],"task_ref":""}'
        )
        claude_svc.understand_message("hello")
    call_kwargs = gc.return_value.chat.completions.create.call_args[1]
    assert call_kwargs["max_tokens"] == 400


def test_chat_intent_returns_no_extra_tasks():
    result = _understand({"intent": "chat", "task": None, "extra_tasks": [], "task_ref": ""})
    assert result["intent"] == "chat"
    assert result["extra_tasks"] == []
    assert result["task"] is None
