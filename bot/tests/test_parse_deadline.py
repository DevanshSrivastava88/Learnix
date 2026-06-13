"""parse_deadline deterministic fast-path (relative phrases, skip words, ISO)."""
from unittest.mock import patch
from datetime import datetime, date, timedelta

with patch("supabase_svc.create_client"):
    import claude_svc


def _days_out(iso):
    return (date.fromisoformat(iso) - date.today()).days


def test_skip_words_return_none():
    for w in ("-", "no", "none", "skip", "no deadline", "whenever"):
        assert claude_svc.parse_deadline(w) is None


def test_iso_passthrough():
    future = (date.today() + timedelta(days=20)).isoformat()
    assert claude_svc.parse_deadline(future) == future


def test_next_month_about_30_days():
    assert _days_out(claude_svc.parse_deadline("next month")) == 30


def test_next_week_7_days():
    assert _days_out(claude_svc.parse_deadline("next week")) == 7


def test_by_prefix_stripped():
    assert _days_out(claude_svc.parse_deadline("in 2 weeks")) == 14


def test_n_units():
    assert _days_out(claude_svc.parse_deadline("10 days")) == 10
    assert _days_out(claude_svc.parse_deadline("3 weeks")) == 21
    assert _days_out(claude_svc.parse_deadline("2 months")) == 60
