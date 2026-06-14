"""Deterministic cleanup in extract_goal_name_from_message — the LLM is mocked,
so these test the regex strip that recovers a clean goal name from a mangled
8B answer ("delete my french goal" must yield "french", not "delete french")."""
from unittest.mock import patch

import claude_svc


def _name(llm_value: str) -> str:
    with patch("claude_svc._ask_json", return_value={"goal_name": llm_value}):
        return claude_svc.extract_goal_name_from_message("whatever")


def test_strips_leading_delete_verb_and_my_and_trailing_goal():
    assert _name("delete my french goal") == "french"


def test_strips_leading_pause_verb():
    assert _name("pause my Machine Learning") == "Machine Learning"


def test_strips_my_prefix_and_goal_suffix():
    assert _name("My Python Goal") == "Python"


def test_strips_remove_and_the():
    assert _name("remove the Spanish goal") == "Spanish"


def test_clean_name_passthrough():
    assert _name("React") == "React"


def test_multiword_name_preserved():
    assert _name("edit my Data Structures goal") == "Data Structures"


def test_non_dict_result_is_empty():
    with patch("claude_svc._ask_json", return_value="oops"):
        assert claude_svc.extract_goal_name_from_message("x") == ""
