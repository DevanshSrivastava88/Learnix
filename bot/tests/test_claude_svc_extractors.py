"""Unit tests for untested claude_svc extractor functions."""
from unittest.mock import patch

with patch("supabase_svc.create_client"):
    import claude_svc


# ---------------------------------------------------------------------------
# extract_task_name_from_message
# ---------------------------------------------------------------------------

def test_extract_task_name_basic():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "workout"}):
        assert claude_svc.extract_task_name_from_message("I finished my workout") == "workout"


def test_extract_task_name_strips_whitespace():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "  meditation  "}):
        assert claude_svc.extract_task_name_from_message("skip meditation today") == "meditation"


def test_extract_task_name_returns_empty_on_bare_done():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": ""}):
        assert claude_svc.extract_task_name_from_message("done") == ""


def test_extract_task_name_returns_empty_on_none_string():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "none"}):
        assert claude_svc.extract_task_name_from_message("skip it today") == ""


def test_extract_task_name_returns_empty_on_null_string():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "null"}):
        assert claude_svc.extract_task_name_from_message("skip that") == ""


def test_extract_task_name_returns_empty_on_non_dict():
    with patch.object(claude_svc, "_ask_json", return_value="bad response"):
        assert claude_svc.extract_task_name_from_message("done with stuff") == ""


def test_extract_task_name_missing_key_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value={}):
        assert claude_svc.extract_task_name_from_message("done") == ""


# ---------------------------------------------------------------------------
# extract_manage_goal_action
# ---------------------------------------------------------------------------

def test_extract_manage_goal_action_delete():
    with patch.object(claude_svc, "_ask_json", return_value={"action": "delete"}):
        assert claude_svc.extract_manage_goal_action("delete my Python goal") == "delete"


def test_extract_manage_goal_action_pause():
    with patch.object(claude_svc, "_ask_json", return_value={"action": "pause"}):
        assert claude_svc.extract_manage_goal_action("pause my React goal") == "pause"


def test_extract_manage_goal_action_edit():
    with patch.object(claude_svc, "_ask_json", return_value={"action": "edit"}):
        assert claude_svc.extract_manage_goal_action("edit my ML goal") == "edit"


def test_extract_manage_goal_action_strips_whitespace():
    with patch.object(claude_svc, "_ask_json", return_value={"action": "  resume  "}):
        assert claude_svc.extract_manage_goal_action("resume my Python goal") == "resume"


def test_extract_manage_goal_action_non_dict_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value="unclear"):
        assert claude_svc.extract_manage_goal_action("do something with my goal") == ""


def test_extract_manage_goal_action_missing_key_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value={}):
        assert claude_svc.extract_manage_goal_action("something") == ""


# ---------------------------------------------------------------------------
# extract_set_time_info
# ---------------------------------------------------------------------------

def test_extract_set_time_info_study():
    with patch.object(claude_svc, "_ask_json", return_value={"time_type": "study", "time_value": "21:00"}):
        result = claude_svc.extract_set_time_info("I want to study at 9pm")
    assert result["time_type"] == "study"
    assert result["time_value"] == "21:00"


def test_extract_set_time_info_morning():
    with patch.object(claude_svc, "_ask_json", return_value={"time_type": "morning", "time_value": "08:00"}):
        result = claude_svc.extract_set_time_info("wake me up at 8am")
    assert result["time_type"] == "morning"
    assert result["time_value"] == "08:00"


def test_extract_set_time_info_eod():
    with patch.object(claude_svc, "_ask_json", return_value={"time_type": "eod", "time_value": "23:00"}):
        result = claude_svc.extract_set_time_info("I usually sleep at 11pm")
    assert result["time_type"] == "eod"
    assert result["time_value"] == "23:00"


def test_extract_set_time_info_non_dict_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value="bad"):
        result = claude_svc.extract_set_time_info("set something")
    assert result == {"time_type": "", "time_value": ""}


def test_extract_set_time_info_missing_keys_returns_empty_strings():
    with patch.object(claude_svc, "_ask_json", return_value={}):
        result = claude_svc.extract_set_time_info("set something")
    assert result["time_type"] == ""
    assert result["time_value"] == ""


# ---------------------------------------------------------------------------
# extract_reschedule_info
# ---------------------------------------------------------------------------

def test_extract_reschedule_info_basic():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "workout", "time": "06:00"}):
        result = claude_svc.extract_reschedule_info("remind me about workout at 6am")
    assert result["task_name"] == "workout"
    assert result["time"] == "06:00"


def test_extract_reschedule_info_strips_whitespace():
    with patch.object(claude_svc, "_ask_json", return_value={"task_name": "  reading  ", "time": "  20:00  "}):
        result = claude_svc.extract_reschedule_info("move my reading reminder to 8pm")
    assert result["task_name"] == "reading"
    assert result["time"] == "20:00"


def test_extract_reschedule_info_non_dict_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value=None):
        result = claude_svc.extract_reschedule_info("move the thing")
    assert result == {"task_name": "", "time": ""}


def test_extract_reschedule_info_missing_keys_returns_empty_strings():
    with patch.object(claude_svc, "_ask_json", return_value={}):
        result = claude_svc.extract_reschedule_info("reschedule it")
    assert result["task_name"] == ""
    assert result["time"] == ""


# ---------------------------------------------------------------------------
# extract_add_topic_info
# ---------------------------------------------------------------------------

def test_extract_add_topic_info_with_goal():
    with patch.object(claude_svc, "_ask_json", return_value={"topic_name": "Recursion", "goal_name": "Python"}):
        result = claude_svc.extract_add_topic_info("add recursion to my Python goal")
    assert result["topic_name"] == "Recursion"
    assert result["goal_name"] == "Python"


def test_extract_add_topic_info_without_goal():
    with patch.object(claude_svc, "_ask_json", return_value={"topic_name": "Binary Trees", "goal_name": ""}):
        result = claude_svc.extract_add_topic_info("add topic Binary Trees")
    assert result["topic_name"] == "Binary Trees"
    assert result["goal_name"] == ""


def test_extract_add_topic_info_strips_whitespace():
    with patch.object(claude_svc, "_ask_json", return_value={"topic_name": "  Decorators  ", "goal_name": "  Python  "}):
        result = claude_svc.extract_add_topic_info("add Decorators to Python")
    assert result["topic_name"] == "Decorators"
    assert result["goal_name"] == "Python"


def test_extract_add_topic_info_non_dict_returns_empty():
    with patch.object(claude_svc, "_ask_json", return_value="nope"):
        result = claude_svc.extract_add_topic_info("add something")
    assert result == {"topic_name": "", "goal_name": ""}


def test_extract_add_topic_info_missing_keys_returns_empty_strings():
    with patch.object(claude_svc, "_ask_json", return_value={}):
        result = claude_svc.extract_add_topic_info("add something")
    assert result["topic_name"] == ""
    assert result["goal_name"] == ""


# ---------------------------------------------------------------------------
# daily_summary
# ---------------------------------------------------------------------------

def test_daily_summary_returns_string():
    with patch.object(claude_svc, "_ask", return_value="Good morning! Keep going 🚀"):
        result = claude_svc.daily_summary({"streak": 5, "topic": "OOP"})
    assert result == "Good morning! Keep going 🚀"


def test_daily_summary_includes_status_in_prompt():
    captured = []

    def fake_ask(prompt, max_tokens=1024):
        captured.append(prompt)
        return "summary"

    with patch.object(claude_svc, "_ask", side_effect=fake_ask):
        claude_svc.daily_summary({"streak": 3})

    assert "streak" in captured[0]
