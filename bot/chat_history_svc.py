"""Persistent chat history — survives deploys/restarts. One row per line."""
import logging
from supabase_svc import get_client

logger = logging.getLogger(__name__)

MAX_LINES = 12


def load_history(user_id: int) -> list[str]:
    """Return the last MAX_LINES history lines, oldest first."""
    try:
        res = (get_client().table("chat_history")
               .select("line")
               .eq("user_id", user_id)
               .order("created_at", desc=True)
               .limit(MAX_LINES)
               .execute())
        return [r["line"] for r in reversed(res.data or [])]
    except Exception as e:
        logger.error(f"load_history failed for {user_id}: {e}")
        return []


def save_line(user_id: int, line: str) -> None:
    try:
        get_client().table("chat_history").insert(
            {"user_id": user_id, "line": line[:500]}
        ).execute()
    except Exception as e:
        logger.error(f"save_line failed for {user_id}: {e}")


def cleanup_old(days: int = 7) -> None:
    """Purge history rows older than N days — context never reaches back that far."""
    from datetime import datetime, timezone, timedelta
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        get_client().table("chat_history").delete().lt("created_at", cutoff).execute()
    except Exception as e:
        logger.error(f"chat_history cleanup failed: {e}")


class DbHistory(list):
    """List that write-through persists appends to the chat_history table."""

    def __init__(self, user_id: int, items: list[str]):
        super().__init__(items)
        self._user_id = user_id

    def append(self, line: str) -> None:
        super().append(line)
        save_line(self._user_id, line)
