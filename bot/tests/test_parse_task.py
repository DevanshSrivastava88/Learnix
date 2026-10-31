"""Unit tests for claude_svc.parse_task — title post-processing logic.

The LLM call is mocked; tests cover the deterministic regex cleanup that
runs after the LLM responds: verb-prefix stripping, type-word stripping,
time-expression stripping from the title field.
"""
from unittest.mock import patch

with patch("supabase_svc.create_client"):
    import claude_svc


def _parse(llm_response: dict) -> dict:
    """Call parse_task with the given dict as the mocked LLM JSON response."""
    with patch.object(claude_svc, "_ask_json", return_value=llm_response):
        return claude_svc.parse_task("any text")


# ── basic passthrough ────────────────────────────────────────────────────────

def test_returns_dict_on_valid_llm_response():
    result = _parse({"type": "reminder", "title": "Call Mom", "time_str": ""})
    assert isinstance(result, dict)
    assert result["type"] == "reminder"


def test_returns_empty_dict_on_non_dict_response():
    with patch.object(claude_svc, "_ask_json", return_value=None):
        assert claude_svc.parse_task("text") == {}


def test_returns_empty_dict_on_list_response():
    with patch.object(claude_svc, "_ask_json", return_value=["bad"]):
        assert claude_svc.parse_task("text") == {}


def test_returns_empty_dict_on_string_response():
    with patch.object(claude_svc, "_ask_json", return_value="not a dict"):
        assert claude_svc.parse_task("text") == {}


# ── verb-prefix stripping ────────────────────────────────────────────────────

def test_strips_add_prefix():
    result = _parse({"type": "reminder", "title": "add Gym", "time_str": ""})
    assert result["title"] == "Gym"


def test_strips_track_prefix():
    result = _parse({"type": "habit", "title": "Track Water Intake", "time_str": ""})
    assert result["title"] == "Water Intake"


def test_strips_remind_me_to_prefix():
    result = _parse({"type": "reminder", "title": "Remind Me To Call Dad", "time_str": ""})
    assert result["title"] == "Call Dad"


def test_strips_remind_me_about_prefix():
    result = _parse({"type": "reminder", "title": "remind me about meeting", "time_str": ""})
    assert result["title"] == "meeting"


def test_strips_schedule_prefix():
    result = _parse({"type": "reminder", "title": "Schedule Doctor Appointment", "time_str": ""})
    assert result["title"] == "Doctor Appointment"


def test_strips_create_prefix():
    result = _parse({"type": "reminder", "title": "Create Budget Report", "time_str": ""})
    assert result["title"] == "Budget Report"


def test_clean_title_unchanged():
    result = _parse({"type": "habit", "title": "Morning Run", "time_str": ""})
    assert result["title"] == "Morning Run"


# ── type-word stripping ──────────────────────────────────────────────────────

def test_strips_habit_prefix():
    result = _parse({"type": "habit", "title": "Habit Meditation", "time_str": ""})
    assert result["title"] == "Meditation"


def test_strips_habbit_typo_prefix():
    result = _parse({"type": "habit", "title": "habbit gym session", "time_str": ""})
    assert result["title"] == "gym session"


def test_strips_daily_prefix():
    result = _parse({"type": "habit", "title": "Daily Journaling", "time_str": ""})
    assert result["title"] == "Journaling"


# ── time-expression stripping ────────────────────────────────────────────────

def test_strips_at_pm_suffix():
    result = _parse({"type": "reminder", "title": "Meeting at 6pm", "time_str": "6pm"})
    assert "6pm" not in result["title"]
    assert "Meeting" in result["title"]


def test_strips_at_24h_time_suffix():
    result = _parse({"type": "reminder", "title": "Call Shreyash at 18:00", "time_str": "18:00"})
    assert "18:00" not in result["title"]
    assert "Call Shreyash" in result["title"]


def test_strips_embedded_time_with_colon_format():
    result = _parse({"type": "reminder", "title": "Daily standup 09:30 AM", "time_str": "9:30am"})
    assert "09:30" not in result["title"]


# ── non-title fields passed through unchanged ────────────────────────────────

def test_time_str_and_type_preserved():
    result = _parse({"type": "habit", "title": "Workout", "time_str": "8am",
                     "recurrence_days": 1, "clarify": ""})
    assert result["time_str"] == "8am"
    assert result["type"] == "habit"
    assert result["recurrence_days"] == 1


def test_empty_title_returns_without_title_key_override():
    # LLM returns empty title — post-processing skips the reassignment
    result = _parse({"type": "reminder", "title": "", "time_str": ""})
    assert result["title"] == ""
