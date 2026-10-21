"""Tests for scheduler.get_missed_yesterday (zero prior coverage).

Covers: empty result, task done yesterday excluded, undone tasks with
next_reminder_at today/tomorrow included, no-next_at guard, case-insensitive
title match, missing note field handled, partial-done multi-task, and None
data from DB handled safely.
"""
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import date, datetime, timedelta

import pytz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with patch("supabase_svc.create_client"):
    import scheduler

IST = pytz.timezone("Asia/Kolkata")


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_client(done_rows=None, task_rows=None):
    """Mock Supabase client for get_missed_yesterday's two queries."""
    c = MagicMock()

    def _table(name):
        tbl = MagicMock()
        ex = MagicMock()
        if name == "activity_log":
            ex.data = done_rows if done_rows is not None else []
            # .select().eq().eq().eq().execute()
            (tbl.select.return_value
               .eq.return_value
               .eq.return_value
               .eq.return_value
               .execute.return_value) = ex
        else:
            ex.data = task_rows if task_rows is not None else []
            # .select().eq().eq().in_().execute()
            (tbl.select.return_value
               .eq.return_value
               .eq.return_value
               .in_.return_value
               .execute.return_value) = ex
        return tbl

    c.table.side_effect = _table
    return c


def _ist_today_9am() -> str:
    return datetime.now(IST).replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


def _ist_tomorrow_9am() -> str:
    return (datetime.now(IST).replace(hour=9, minute=0, second=0, microsecond=0)
            + timedelta(days=1)).isoformat()


def _ist_yesterday_9am() -> str:
    return (datetime.now(IST).replace(hour=9, minute=0, second=0, microsecond=0)
            - timedelta(days=1)).isoformat()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_no_tasks_returns_empty():
    c = _make_client(done_rows=[], task_rows=[])
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []


def test_task_done_yesterday_not_missed():
    """Title in yesterday's activity_log → excluded from missed."""
    done_rows = [{"note": "Morning run"}]
    task_rows = [{"title": "Morning run", "task_type": "habit",
                  "next_reminder_at": _ist_today_9am()}]
    c = _make_client(done_rows=done_rows, task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []


def test_task_not_done_next_at_today_is_missed():
    """Undone task with next_reminder_at = today appears in missed list."""
    task_rows = [{"title": "Meditate", "task_type": "habit",
                  "next_reminder_at": _ist_today_9am()}]
    c = _make_client(done_rows=[], task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        result = scheduler.get_missed_yesterday(42)
    assert "Meditate" in result


def test_task_not_done_next_at_tomorrow_is_missed():
    """Undone task rescheduled to tomorrow still appears in missed list."""
    task_rows = [{"title": "Evening walk", "task_type": "habit",
                  "next_reminder_at": _ist_tomorrow_9am()}]
    c = _make_client(done_rows=[], task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        result = scheduler.get_missed_yesterday(42)
    assert "Evening walk" in result


def test_task_with_no_next_reminder_not_missed():
    """next_reminder_at=None means unscheduled — never added to missed."""
    task_rows = [{"title": "Unscheduled habit", "task_type": "habit",
                  "next_reminder_at": None}]
    c = _make_client(done_rows=[], task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []


def test_task_with_stale_next_at_in_past_not_missed():
    """Task whose next_reminder_at is still in the past (not rescheduled) is excluded."""
    task_rows = [{"title": "Old habit", "task_type": "habit",
                  "next_reminder_at": _ist_yesterday_9am()}]
    c = _make_client(done_rows=[], task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []


def test_done_check_is_case_insensitive():
    """Title match against done_notes is case-insensitive."""
    done_rows = [{"note": "MORNING RUN"}]
    task_rows = [{"title": "Morning run", "task_type": "habit",
                  "next_reminder_at": _ist_today_9am()}]
    c = _make_client(done_rows=done_rows, task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []


def test_done_row_without_note_field_not_crash():
    """Rows in activity_log that lack a 'note' key are silently skipped."""
    done_rows = [{}]
    task_rows = [{"title": "Meditate", "task_type": "habit",
                  "next_reminder_at": _ist_today_9am()}]
    c = _make_client(done_rows=done_rows, task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        result = scheduler.get_missed_yesterday(42)
    assert "Meditate" in result


def test_multiple_tasks_only_undone_returned():
    """Only undone tasks appear; done tasks are excluded."""
    done_rows = [{"note": "Yoga"}]
    task_rows = [
        {"title": "Yoga",        "task_type": "habit", "next_reminder_at": _ist_today_9am()},
        {"title": "Cold shower", "task_type": "habit", "next_reminder_at": _ist_today_9am()},
    ]
    c = _make_client(done_rows=done_rows, task_rows=task_rows)
    with patch("supabase_svc.get_client", return_value=c):
        result = scheduler.get_missed_yesterday(42)
    assert "Yoga" not in result
    assert "Cold shower" in result


def test_none_data_from_db_handled_safely():
    """If DB returns None for data, function returns [] without crashing."""
    c = MagicMock()
    ex = MagicMock()
    ex.data = None
    # Both table queries chain back to the same mock return path
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = ex
    c.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = ex
    with patch("supabase_svc.get_client", return_value=c):
        assert scheduler.get_missed_yesterday(42) == []
