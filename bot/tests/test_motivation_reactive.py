"""Reactive motivation: struggle detection + comeback-on-skip note."""
from unittest.mock import patch
import motivation_svc as mot


def test_struggle_detects_failure_phrases():
    for t in ["i keep failing", "i suck at this", "i give up", "i'm a failure",
              "i messed up again", "this is too hard", "i can't keep up",
              "i'm so behind", "i feel like quitting", "honestly i feel like giving up",
              "i'm so overwhelmed", "i can't do this anymore", "it's too much"]:
        assert mot.is_struggle_message(t), t


def test_struggle_ignores_normal_messages():
    for t in ["add gym at 6pm", "how far am i on python", "what do i have today",
              "i finished the report", "remind me to call mom", "let's study"]:
        assert not mot.is_struggle_message(t), t


def test_comeback_note_scales_with_skips():
    with patch.object(mot, "_count_skips_today", return_value=0):
        assert mot.comeback_note_on_skip(1) == ""
    with patch.object(mot, "_count_skips_today", return_value=2):
        assert "clean slate" in mot.comeback_note_on_skip(1).lower()
    with patch.object(mot, "_count_skips_today", return_value=4):
        assert "rough day" in mot.comeback_note_on_skip(1).lower()


def test_comeback_note_safe_on_db_error():
    with patch.object(mot, "_count_skips_today", side_effect=Exception("db down")):
        assert mot.comeback_note_on_skip(1) == ""


def test_generate_struggle_support_calls_llm_with_offer():
    captured = {}
    def fake_ask(prompt, max_tokens=160):
        captured["p"] = prompt
        return "That sounds heavy. Want me to pause a habit? 💛"
    with patch.object(mot.claude_svc, "_ask", fake_ask), \
         patch("settings_svc.get_settings", return_value={"streak": 5}), \
         patch("tasks.svc.list_tasks", return_value=[]):
        out = mot.generate_struggle_support(1, "i keep failing", "default")
    # The concrete offer is ALWAYS appended deterministically, regardless of the LLM body
    assert "pause a habit" in out.lower() and "lighten the load" in out.lower()
    assert "tomorrow" in out.lower()
    assert "5 days" in captured["p"]                     # prompt references their real streak


def test_struggle_support_offer_survives_llm_failure():
    with patch.object(mot.claude_svc, "_ask", side_effect=Exception("groq down")), \
         patch("settings_svc.get_settings", return_value={"streak": 0}), \
         patch("tasks.svc.list_tasks", return_value=[]):
        out = mot.generate_struggle_support(1, "i give up", "default")
    assert "pause a habit" in out.lower()  # offer attached even when the LLM call fails
