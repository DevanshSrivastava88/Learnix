"""
Shared pytest configuration.

Prevents test-isolation failures caused by test_pending_task_action.py injecting
stub modules into sys.modules at collection time and replacing real module
functions with MagicMocks.

Root cause: test_pending_task_action.py runs module-level code at collection time
that (a) stubs any module name absent from sys.modules, and (b) setattr-replaces
functions on already-loaded modules with MagicMock().  Both effects persist for
the rest of the test session.

Fix:
  1. Pre-import the affected real modules here so they are present in sys.modules
     before test_pending_task_action.py's collection-time check runs.
  2. Snapshot the real tasks.svc callables and restore them via a session-scoped
     autouse fixture, which fires before any test function executes.
"""
from unittest.mock import patch
import pytest


# ── 1. Pre-import real modules ─────────────────────────────────────────────
# conftest.py is imported before any test file, so these will already be in
# sys.modules when test_pending_task_action.py's stub-injection loop runs.
with patch("supabase_svc.create_client"):
    import settings_svc        # noqa: F401
    import scheduler           # noqa: F401
    from study import handlers # noqa: F401
    from tasks import svc as _tasks_svc


# ── 2. Snapshot real callables before test_pending_task_action clobbers them ──
# test_pending_task_action.py setattr-replaces functions on already-loaded modules
# with MagicMock() at collection time.  We capture the originals here and restore
# them before any test function runs.

_REAL_TASKS_FUNS = {
    fn: getattr(_tasks_svc, fn)
    for fn in (
        "list_tasks", "mark_done", "log_skip", "reschedule_task",
        "delete_task", "update_task", "mark_important", "unmark_important",
    )
    if hasattr(_tasks_svc, fn)
}

_REAL_SETTINGS_FUNS = {
    fn: getattr(settings_svc, fn)
    for fn in ("get_settings", "upsert_settings", "update_streak",
               "set_daily_time", "set_morning_brief_time", "set_eod_time",
               "get_all_users")
    if hasattr(settings_svc, fn)
}


@pytest.fixture(autouse=True, scope="session")
def _restore_real_module_functions():
    """Restore real module functions after collection-time MagicMock injection."""
    for fn_name, fn in _REAL_TASKS_FUNS.items():
        setattr(_tasks_svc, fn_name, fn)
    for fn_name, fn in _REAL_SETTINGS_FUNS.items():
        setattr(settings_svc, fn_name, fn)
    yield
