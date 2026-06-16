"""Long-term memory store (exo-cortex port). Backed by Supabase tables
`user_facts` + `mem_events` (migration 015).

Write path runs at SESSION END (see /wrap + idle/daily backstop): one cheap LLM
call extracts durable facts + a typed sentiment timeline from the transcript, then
apply_extraction() dedups/supersedes/inserts here. Read path: memory_brief() renders
a compact block injected into the coach's context (plugs into gather_user_context).

Full-life scope, weighted to 3 dominant pillars: productivity | motivation | addiction.
Never raises — memory must never break the chat. See docs/MEMORY_INTEGRATION.md.
"""
import logging

from supabase_svc import get_client

logger = logging.getLogger(__name__)

PILLARS = {"productivity", "motivation", "addiction", "general"}
EVENT_TYPES = {"mood", "progress", "setback", "milestone", "insight", "prediction", "event"}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _pillar(p) -> str:
    p = (p or "general").strip().lower()
    return p if p in PILLARS else "general"


# ---------------------------------------------------------------- read

def load_facts(user_id: int) -> list[dict]:
    """Active (non-superseded) facts for this user, newest first."""
    try:
        res = (get_client().table("user_facts")
               .select("id, text, pillar, created_at")
               .eq("user_id", user_id).eq("status", "active")
               .order("created_at", desc=True).execute())
        return res.data or []
    except Exception as e:
        logger.error(f"load_facts failed for {user_id}: {e}")
        return []


def load_events(user_id: int, limit: int = 10) -> list[dict]:
    """Recent timeline events, oldest-first (for prompt/display)."""
    try:
        res = (get_client().table("mem_events")
               .select("type, summary, detail, pillar, sentiment, created_at")
               .eq("user_id", user_id)
               .order("created_at", desc=True).limit(limit).execute())
        return list(reversed(res.data or []))
    except Exception as e:
        logger.error(f"load_events failed for {user_id}: {e}")
        return []


def memory_brief(user_id: int) -> str:
    """Compact prompt block of what we know — facts (by pillar) + recent timeline.
    Empty string when nothing stored, so the coach never invents memory."""
    facts = load_facts(user_id)
    events = load_events(user_id, 8)
    if not facts and not events:
        return ""
    lines = []
    if facts:
        lines.append("KNOWN FACTS (true, keep in mind; never invent beyond these):")
        for f in facts:
            tag = f["pillar"] if f.get("pillar") and f["pillar"] != "general" else ""
            lines.append(f"  - {f['text']}" + (f"  [{tag}]" if tag else ""))
    if events:
        lines.append("RECENT TIMELINE (newest last):")
        for ev in events:
            s = ev.get("sentiment")
            mood = f" [{s:+.1f}]" if isinstance(s, (int, float)) and s else ""
            lines.append(f"  - ({ev['type']}) {ev['summary']}{mood}")
    return "\n".join(lines)


# ---------------------------------------------------------------- sessions

def save_session(user_id: int, summary: str, mood: str = "", open_threads: list | None = None) -> None:
    """Store one session recap (from extract_memory's summary/mood/open_threads)."""
    if not (summary or "").strip():
        return
    try:
        get_client().table("mem_sessions").insert({
            "user_id": user_id, "summary": summary.strip(),
            "mood": (mood or "").strip() or None,
            "open_threads": open_threads or [],
        }).execute()
    except Exception as e:
        logger.error(f"save_session failed for {user_id}: {e}")


def last_session(user_id: int) -> dict | None:
    """Most recent session recap, or None."""
    try:
        res = (get_client().table("mem_sessions")
               .select("summary, mood, open_threads, created_at")
               .eq("user_id", user_id)
               .order("created_at", desc=True).limit(1).execute())
        return (res.data or [None])[0]
    except Exception as e:
        logger.error(f"last_session failed for {user_id}: {e}")
        return None


def welcome_back(user_id: int) -> str:
    """A 'where we left off' line for the next session, or '' if none / fresh."""
    s = last_session(user_id)
    if not s:
        return ""
    threads = s.get("open_threads") or []
    if threads:
        return f"Last time we left off on: {threads[0]} — want to pick up there?"
    if s.get("summary"):
        return f"Last time: {s['summary']}"
    return ""


# ---------------------------------------------------------------- write

def _insert_fact(user_id: int, text: str, pillar: str) -> str | None:
    try:
        res = (get_client().table("user_facts")
               .insert({"user_id": user_id, "text": text.strip(), "pillar": _pillar(pillar)})
               .execute())
        return (res.data or [{}])[0].get("id")
    except Exception as e:
        logger.error(f"_insert_fact failed for {user_id}: {e}")
        return None


def apply_extraction(user_id: int, data: dict) -> dict:
    """Persist an extractor payload. Returns counts of what changed.

    data keys: facts_add[{text,pillar}], fact_updates[{old,new,pillar}],
    events[{type,summary,detail,pillar,sentiment,intensity}].
    Never raises.
    """
    changes = {"facts_added": 0, "facts_updated": 0, "events": 0}
    if not isinstance(data, dict):
        return changes

    existing = load_facts(user_id)
    seen = {_norm(f["text"]): f for f in existing}

    # new facts (skip dupes)
    for f in data.get("facts_add") or []:
        text = (f.get("text") or "").strip() if isinstance(f, dict) else str(f).strip()
        if not text or _norm(text) in seen:
            continue
        pillar = f.get("pillar") if isinstance(f, dict) else "general"
        fid = _insert_fact(user_id, text, pillar)
        if fid:
            seen[_norm(text)] = {"id": fid, "text": text}
            changes["facts_added"] += 1

    # fact corrections (our fix for Atlas's append-only gap): supersede old -> new
    for u in data.get("fact_updates") or []:
        if not isinstance(u, dict):
            continue
        old_text = (u.get("old") or "").strip()
        new_text = (u.get("new") or "").strip()
        if not new_text:
            continue
        old = seen.get(_norm(old_text))
        # fuzzy match if exact-normalized miss
        if not old and old_text:
            no = _norm(old_text)
            for k, v in seen.items():
                if no and (no in k or k in no):
                    old = v
                    break
        new_id = _insert_fact(user_id, new_text, u.get("pillar"))
        if not new_id:
            continue
        seen[_norm(new_text)] = {"id": new_id, "text": new_text}
        changes["facts_updated"] += 1
        if old and old.get("id"):
            try:
                (get_client().table("user_facts")
                 .update({"status": "superseded", "superseded_by": new_id})
                 .eq("id", old["id"]).eq("user_id", user_id).execute())
            except Exception as e:
                logger.error(f"supersede fact failed for {user_id}: {e}")

    # timeline events
    for ev in data.get("events") or []:
        if not isinstance(ev, dict):
            continue
        summary = (ev.get("summary") or "").strip()
        if not summary:
            continue
        etype = (ev.get("type") or "event").strip().lower()
        if etype not in EVENT_TYPES:
            etype = "event"
        try:
            sentiment = float(ev.get("sentiment") or 0.0)
        except (TypeError, ValueError):
            sentiment = 0.0
        try:
            intensity = float(ev.get("intensity") or 0.0)
        except (TypeError, ValueError):
            intensity = 0.0
        try:
            (get_client().table("mem_events").insert({
                "user_id": user_id, "type": etype, "summary": summary,
                "detail": (ev.get("detail") or "").strip() or None,
                "pillar": _pillar(ev.get("pillar")),
                "sentiment": max(-1.0, min(1.0, sentiment)),
                "intensity": max(0.0, min(1.0, intensity)),
            }).execute())
            changes["events"] += 1
        except Exception as e:
            logger.error(f"insert event failed for {user_id}: {e}")

    return changes
