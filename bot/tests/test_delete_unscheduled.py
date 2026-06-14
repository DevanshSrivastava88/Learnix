"""Routing guard for 'delete unscheduled tasks' — must NOT be read as a task
named 'unscheduled' (disambiguation loop) or as clear_data (wipe everything).
Mirrors the deterministic regex in bot.handle_free_text."""
import re

import pytest

# same pattern used in handle_free_text
_PAT = re.compile(r'\b(delete|remove|clear|wipe|del)\b.{0,20}\bunscheduled\b', re.IGNORECASE)


@pytest.mark.parametrize("text", [
    "delete unscheduled tasks",
    "delete uncheduled tasks".replace("uncheduled", "unscheduled"),
    "remove unscheduled",
    "clear unscheduled tasks",
    "delete all unscheduled tasks",
    "wipe my unscheduled tasks",
    "del unscheduled",
])
def test_matches_bulk_delete_unscheduled(text):
    assert _PAT.search(text)


@pytest.mark.parametrize("text", [
    "delete feed cat",
    "add unscheduled meeting",          # adding, not deleting
    "show my unscheduled tasks",        # viewing
    "set feed cat to 8pm",
    "what are my unscheduled tasks",
])
def test_does_not_match_other_intents(text):
    assert not _PAT.search(text)
