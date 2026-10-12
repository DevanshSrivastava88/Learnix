"""Unit tests for claude_svc study/breakdown functions with zero prior coverage:
revise_subtasks, teach_topic, generate_quiz, score_answer."""
from unittest.mock import patch, MagicMock
import pytest

with patch("supabase_svc.create_client"):
    import claude_svc


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_completion(content: str):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    return r


# ── revise_subtasks ───────────────────────────────────────────────────────────

def test_revise_subtasks_returns_revised_list():
    revised = ["Warmup 5 min", "Push-ups 3 sets", "Cool down stretch"]
    with patch.object(claude_svc, "_ask_json_array", return_value=revised):
        result = claude_svc.revise_subtasks("Morning workout", ["Warmup", "Push-ups"], "add cool down")
    assert result == revised


def test_revise_subtasks_filters_empty_strings():
    with patch.object(claude_svc, "_ask_json_array", return_value=["Step A", "", "Step B", "  "]):
        result = claude_svc.revise_subtasks("Task", ["Step A", "Step B"], "fix it")
    assert result == ["Step A", "Step B"]


def test_revise_subtasks_strips_whitespace_from_items():
    with patch.object(claude_svc, "_ask_json_array", return_value=["  Warmup  ", "  Push-ups  "]):
        result = claude_svc.revise_subtasks("Workout", ["Warmup"], "tweak it")
    assert result == ["Warmup", "Push-ups"]


def test_revise_subtasks_truncates_to_10():
    long_list = [f"Step {i}" for i in range(15)]
    with patch.object(claude_svc, "_ask_json_array", return_value=long_list):
        result = claude_svc.revise_subtasks("Big task", ["a", "b"], "add more")
    assert len(result) == 10
    assert result == [f"Step {i}" for i in range(10)]


def test_revise_subtasks_raises_on_non_list():
    with patch.object(claude_svc, "_ask_json_array", return_value={"error": "bad"}):
        with pytest.raises(ValueError, match="Expected JSON array"):
            claude_svc.revise_subtasks("Task", ["Step 1"], "change it")


def test_revise_subtasks_prompt_includes_parent():
    captured = []

    def fake_array(prompt):
        captured.append(prompt)
        return ["Step 1"]

    with patch.object(claude_svc, "_ask_json_array", side_effect=fake_array):
        claude_svc.revise_subtasks("Morning Meditation", ["Breathe", "Focus"], "be more specific")
    assert "Morning Meditation" in captured[0]


def test_revise_subtasks_prompt_includes_feedback():
    captured = []

    def fake_array(prompt):
        captured.append(prompt)
        return ["Step 1"]

    with patch.object(claude_svc, "_ask_json_array", side_effect=fake_array):
        claude_svc.revise_subtasks("Task", ["a"], "remove step 2 and add stretching at the end")
    assert "remove step 2 and add stretching at the end" in captured[0]


def test_revise_subtasks_prompt_numbers_existing_steps():
    captured = []

    def fake_array(prompt):
        captured.append(prompt)
        return ["Step 1", "Step 2"]

    with patch.object(claude_svc, "_ask_json_array", side_effect=fake_array):
        claude_svc.revise_subtasks("Build shelf", ["Buy nails", "Sand wood", "Paint"], "change order")
    assert "1. Buy nails" in captured[0]
    assert "2. Sand wood" in captured[0]
    assert "3. Paint" in captured[0]


def test_revise_subtasks_coerces_non_string_items():
    with patch.object(claude_svc, "_ask_json_array", return_value=[1, 2.5, "actual step"]):
        result = claude_svc.revise_subtasks("Task", ["a"], "fix it")
    assert "1" in result
    assert "2.5" in result
    assert "actual step" in result


def test_revise_subtasks_with_empty_existing_steps():
    with patch.object(claude_svc, "_ask_json_array", return_value=["Step 1", "Step 2"]):
        result = claude_svc.revise_subtasks("New task", [], "add steps from scratch")
    assert result == ["Step 1", "Step 2"]


# ── teach_topic ───────────────────────────────────────────────────────────────

def test_teach_topic_returns_string():
    with patch.object(claude_svc, "_ask", return_value="Here is an explanation of generators."):
        result = claude_svc.teach_topic("Python generators")
    assert result == "Here is an explanation of generators."


def test_teach_topic_no_notes_omits_notes_from_prompt():
    captured = []

    def fake_ask(prompt, max_tokens=1024):
        captured.append(prompt)
        return "explanation"

    with patch.object(claude_svc, "_ask", side_effect=fake_ask):
        claude_svc.teach_topic("Closures")
    assert "My notes" not in captured[0]
    assert "Closures" in captured[0]


def test_teach_topic_with_notes_includes_them_in_prompt():
    captured = []

    def fake_ask(prompt, max_tokens=1024):
        captured.append(prompt)
        return "explanation"

    with patch.object(claude_svc, "_ask", side_effect=fake_ask):
        claude_svc.teach_topic("Closures", notes="Captures outer scope variables.")
    assert "My notes" in captured[0]
    assert "Captures outer scope variables." in captured[0]


# ── generate_quiz ─────────────────────────────────────────────────────────────

def test_generate_quiz_returns_list_of_dicts():
    questions = [
        {"question": "What is a closure?", "expected_answer": "A function capturing its enclosing scope."},
        {"question": "Q2", "expected_answer": "A2"},
        {"question": "Q3", "expected_answer": "A3"},
        {"question": "Q4", "expected_answer": "A4"},
        {"question": "Q5", "expected_answer": "A5"},
    ]
    with patch.object(claude_svc, "_ask_json", return_value=questions):
        result = claude_svc.generate_quiz("Closures")
    assert len(result) == 5
    assert all(isinstance(q, dict) for q in result)
    assert result[0]["question"] == "What is a closure?"


def test_generate_quiz_truncates_to_five():
    questions = [{"question": f"Q{i}", "expected_answer": f"A{i}"} for i in range(8)]
    with patch.object(claude_svc, "_ask_json", return_value=questions):
        result = claude_svc.generate_quiz("Python")
    assert len(result) == 5


def test_generate_quiz_raises_on_non_list():
    with patch.object(claude_svc, "_ask_json", return_value={"error": "bad"}):
        with pytest.raises(ValueError, match="expected JSON array"):
            claude_svc.generate_quiz("Python")


# ── score_answer ──────────────────────────────────────────────────────────────

def test_score_answer_returns_dict_with_correct_and_explanation():
    with patch.object(claude_svc, "_ask_json", return_value={"correct": True, "explanation": "Correct!"}):
        result = claude_svc.score_answer("What is OOP?", "Object-oriented programming.", "OOP is a paradigm.")
    assert result["correct"] is True
    assert result["explanation"] == "Correct!"


def test_score_answer_returns_false_for_wrong_answer():
    with patch.object(claude_svc, "_ask_json", return_value={"correct": False, "explanation": "That's not right."}):
        result = claude_svc.score_answer("What is recursion?", "A function calling itself.", "No idea.")
    assert result["correct"] is False


def test_score_answer_passes_all_three_fields_to_prompt():
    captured = []

    def fake_ask_json(prompt, max_tokens=512):
        captured.append(prompt)
        return {"correct": True, "explanation": "ok"}

    with patch.object(claude_svc, "_ask_json", side_effect=fake_ask_json):
        claude_svc.score_answer("What is a list?", "An ordered collection.", "A list holds items.")
    assert "What is a list?" in captured[0]
    assert "An ordered collection." in captured[0]
    assert "A list holds items." in captured[0]
