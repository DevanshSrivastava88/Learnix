"""Study plan engine — offset distribution + on-track status."""
from unittest.mock import patch
from datetime import date, timedelta

with patch("supabase_svc.create_client"):
    from study import svc


def test_offsets_single_topic():
    assert svc._plan_offsets(1, 30) == [0]


def test_offsets_no_target_one_per_day():
    assert svc._plan_offsets(4, 0) == [0, 1, 2, 3]


def test_offsets_spread_evenly_endpoints():
    off = svc._plan_offsets(8, 29)
    assert off[0] == 0 and off[-1] == 29        # first today, last on target
    assert off == sorted(off)                    # monotonic
    assert all(0 <= o <= 29 for o in off)


def test_offsets_more_topics_than_days():
    # 5 topics, 2-day span → clamped within span, still monotonic
    off = svc._plan_offsets(5, 2)
    assert off[0] == 0 and off[-1] == 2 and off == sorted(off)


def test_offsets_empty():
    assert svc._plan_offsets(0, 10) == []


def _goal(**kw):
    base = {"id": "g1", "name": "Spanish", "start_date": date.today().isoformat(),
            "target_date": (date.today() + timedelta(days=9)).isoformat()}
    base.update(kw); return base


def _topic(i, status="not_started", sched_off=0):
    return {"id": f"t{i}", "goal_id": "g1", "title": f"Topic {i}", "status": status,
            "order_index": i, "parent_id": None,
            "scheduled_date": (date.today() + timedelta(days=sched_off)).isoformat()}


def test_plan_status_on_track():
    # topic 0 due today (not overdue), topic 1 future → nothing past-due → on track
    topics = [_topic(0, "not_started", 0), _topic(1, "not_started", 5)]
    with patch.object(svc, "get_goal", return_value=_goal()), \
         patch.object(svc, "list_topics_for_goal", return_value=topics):
        st = svc.get_plan_status("g1")
    assert st["expected"] == 0          # nothing overdue on day 1
    assert st["on_track"] is True
    assert st["today_topic"]["id"] == "t0"   # today's topic surfaced as next up


def test_plan_status_today_topic_not_overdue():
    # day-1 fresh plan, no topic done → must be on track, not "behind"
    topics = [_topic(0, "not_started", 0), _topic(1, "not_started", 4)]
    with patch.object(svc, "get_goal", return_value=_goal()), \
         patch.object(svc, "list_topics_for_goal", return_value=topics):
        st = svc.get_plan_status("g1")
    assert st["on_track"] is True and st["behind_topics"] == []


def test_plan_status_behind():
    # both topics due (scheduled in the past), none done → behind
    topics = [_topic(0, "not_started", -3), _topic(1, "not_started", -1)]
    with patch.object(svc, "get_goal", return_value=_goal()), \
         patch.object(svc, "list_topics_for_goal", return_value=topics):
        st = svc.get_plan_status("g1")
    assert st["expected"] == 2 and st["completed"] == 0
    assert st["on_track"] is False
    assert len(st["behind_topics"]) == 2


def test_plan_status_none_without_plan():
    with patch.object(svc, "get_goal", return_value=_goal(start_date=None)):
        assert svc.get_plan_status("g1") is None
