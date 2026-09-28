"""
Tests for pure functions in tasks/timesheet_handlers.py.

Both _find_habit and _parse_timesheet_input are non-Telegram: no Update/Context
needed. Supabase and Gemini are mocked where required.
"""
from unittest.mock import MagicMock, patch

import pytest

with patch("supabase_svc.create_client"):
    from tasks.timesheet_handlers import _find_habit, _parse_timesheet_input


# ---------------------------------------------------------------------------
# _find_habit
# ---------------------------------------------------------------------------

HABITS = [
    {"id": 1, "title": "Morning Workout", "task_type": "habit"},
    {"id": 2, "title": "Read 10 Pages", "task_type": "habit"},
    {"id": 3, "title": "Meditate", "task_type": "habit"},
]


class TestFindHabit:
    def test_exact_match(self):
        assert _find_habit("Morning Workout", HABITS)["id"] == 1

    def test_case_insensitive_exact(self):
        assert _find_habit("morning workout", HABITS)["id"] == 1

    def test_partial_name_in_title(self):
        # "workout" is a substring of "Morning Workout"
        assert _find_habit("workout", HABITS)["id"] == 1

    def test_title_in_name(self):
        # "Meditate" is a substring of the user's longer phrase
        assert _find_habit("meditate for 10 mins", HABITS)["id"] == 3

    def test_no_match_returns_none(self):
        assert _find_habit("yoga", HABITS) is None

    def test_empty_habits_returns_none(self):
        assert _find_habit("anything", []) is None

    def test_reads_pages_partial(self):
        # "read 10 pages" matches when user says "read pages" (substring of title)
        assert _find_habit("Read 10 Pages", HABITS)["id"] == 2

    def test_mixed_case_habit_name(self):
        assert _find_habit("MEDITATE", HABITS)["id"] == 3


# ---------------------------------------------------------------------------
# _parse_timesheet_input
# ---------------------------------------------------------------------------

class TestParseTimesheetInput:
    def test_returns_dict_from_valid_llm_response(self):
        expected = {"Morning Workout": "8am", "Read 10 Pages": "10pm"}
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value=expected):
            result = _parse_timesheet_input("workout at 8am, reading at 10pm", ["Morning Workout", "Read 10 Pages"])
        assert result == expected

    def test_returns_empty_dict_when_llm_returns_list(self):
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value=[]):
            result = _parse_timesheet_input("some text", ["Morning Workout"])
        assert result == {}

    def test_returns_empty_dict_when_llm_returns_string(self):
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value="bad"):
            result = _parse_timesheet_input("some text", ["Morning Workout"])
        assert result == {}

    def test_returns_empty_dict_when_llm_returns_none(self):
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value=None):
            result = _parse_timesheet_input("some text", ["Morning Workout"])
        assert result == {}

    def test_returns_empty_dict_on_exception(self):
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", side_effect=Exception("api error")):
            result = _parse_timesheet_input("workout at 8am", ["Morning Workout"])
        assert result == {}

    def test_single_habit_parsed(self):
        expected = {"Meditate": "in 30 mins"}
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value=expected):
            result = _parse_timesheet_input("meditate in 30 mins", ["Meditate"])
        assert result == {"Meditate": "in 30 mins"}

    def test_passes_habit_names_and_text_to_llm(self):
        with patch("tasks.timesheet_handlers.claude_svc._ask_json", return_value={}) as mock_ask:
            _parse_timesheet_input("workout at 8am", ["Morning Workout"])
        called_prompt = mock_ask.call_args[0][0]
        assert "Morning Workout" in called_prompt
        assert "workout at 8am" in called_prompt
