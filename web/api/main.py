"""
Learnix web API — multi-user task layer over the existing bot data.

Reuses bot/tasks/svc.py (Supabase) so there is no second source of truth.
Auth is bot-initiated: the user sends /weblogin to the Telegram bot, which
mints a one-time code tied to their user_id. The web verifies that code and
issues a signed session cookie. All task routes are scoped to the session's
user_id — every user sees only their own tasks.
"""
import hashlib
import hmac
import os
from datetime import datetime
import secrets
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- wire in the existing bot package + its env ------------------------------
_HERE = Path(__file__).resolve().parent


def _bot_candidates():
    cands = []
    env = os.environ.get("LEARNIX_BOT_DIR")
    if env:
        cands.append(Path(env))
    if len(_HERE.parents) >= 2:           # local dev: web/api -> repo/bot
        cands.append(_HERE.parents[1] / "bot")
    cands.append(_HERE / "_bot")          # container fallback
    return cands


BOT_DIR = next((c for c in _bot_candidates() if (c / "tasks" / "svc.py").exists()), None)
if BOT_DIR is None:
    raise RuntimeError("Could not locate bot data layer (tasks/svc.py)")
sys.path.insert(0, str(BOT_DIR))
load_dotenv(BOT_DIR / ".env")  # no-op in prod; Railway injects env vars directly

import tasks.svc as tasks_svc            # noqa: E402  (path set above)
import analytics_svc                      # noqa: E402
import settings_svc                       # noqa: E402
from supabase_svc import get_client      # noqa: E402

# Sessions are signed with this secret. Set SESSION_SECRET in prod so sessions
# survive restarts; a random ephemeral one is used otherwise (logs everyone out
# on restart, but never insecure).
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
SESSION_TTL = 30 * 24 * 3600  # 30 days
# TEMPORARY admin bypass: when ADMIN_KEY is set, the login box accepts a code of
# the form "<ADMIN_KEY>:<uid>" to open any user's account without a Telegram code.
# Unset ADMIN_KEY in the Railway env to disable it.
ADMIN_KEY = os.environ.get("ADMIN_KEY")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"  # set 0 for local http

app = FastAPI(title="Learnix Tasks")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- session tokens (HMAC-signed, stateless) ---------------------------------

def _make_token(uid: int) -> str:
    exp = int(time.time()) + SESSION_TTL
    body = f"{uid}.{exp}"
    sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _read_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        uid_s, exp_s, sig = token.rsplit(".", 2)
    except ValueError:
        return None
    body = f"{uid_s}.{exp_s}"
    expected = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    if int(exp_s) < int(time.time()):
        return None
    return int(uid_s)


def get_current_uid(request: Request) -> int:
    uid = _read_token(request.cookies.get("session"))
    if uid is None:
        raise HTTPException(401, "Not logged in")
    return uid


# --- brute-force guard for the short numeric code ----------------------------
# 4 digits = 10k space, so cap wrong guesses per client. In-memory (single
# instance); resets on restart, which is fine for this scale.
_FAIL_WINDOW = 600          # 10 min
_FAIL_MAX = 8               # lock after 8 wrong codes in the window
_fails: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _check_rate(ip: str) -> None:
    now = time.time()
    hits = [t for t in _fails.get(ip, []) if now - t < _FAIL_WINDOW]
    _fails[ip] = hits
    if len(hits) >= _FAIL_MAX:
        raise HTTPException(429, "Too many attempts — wait a bit and send /weblogin again")


def _record_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


# --- shaping -----------------------------------------------------------------

def _is_subtask(title: str) -> bool:
    return " — Step " in (title or "")


def _shape(t: dict) -> dict:
    return {
        "id": t["id"],
        "title": t.get("title", ""),
        "status": t.get("status", "active"),
        "type": t.get("task_type", "task"),
        "due": t.get("next_reminder_at"),
        "recurrence": t.get("recurrence_days"),
        "ordering": t.get("sort_order"),
        "created_at": t.get("created_at"),
    }


def _visible(rows: list) -> list:
    return [_shape(t) for t in rows if not _is_subtask(t.get("title", ""))]


# --- models ------------------------------------------------------------------

class NewTask(BaseModel):
    title: str
    due: str | None = None  # optional ISO datetime to schedule it


class TaskPatch(BaseModel):
    status: str | None = None
    title: str | None = None
    due: str | None = None  # ISO datetime to (re)schedule; "" to unschedule


class LoginCode(BaseModel):
    code: str


class ReorderBody(BaseModel):
    ids: list[str]  # active task ids in the desired top-to-bottom order


# --- auth routes -------------------------------------------------------------

@app.post("/api/auth/verify")
def auth_verify(body: LoginCode, request: Request, response: Response):
    ip = _client_ip(request)
    _check_rate(ip)
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(400, "Enter the code from Telegram")
    # admin bypass: "<ADMIN_KEY>:<uid>" opens that user's account directly.
    if ADMIN_KEY and code.startswith(ADMIN_KEY + ":"):
        try:
            uid = int(code.split(":", 1)[1])
        except ValueError:
            _record_fail(ip)
            raise HTTPException(400, "admin code format is KEY:uid")
        _fails.pop(ip, None)
        response.set_cookie(
            "session", _make_token(uid),
            httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_TTL,
        )
        return {"ok": True, "uid": uid, "admin": True}
    res = get_client().table("web_login_codes").select("*").eq("code", code).limit(1).execute()
    row = res.data[0] if res.data else None
    if not row or row.get("used"):
        _record_fail(ip)
        raise HTTPException(401, "Invalid or already-used code")
    from datetime import datetime, timezone
    try:
        expired = datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc)
    except Exception:
        expired = True
    if expired:
        _record_fail(ip)
        raise HTTPException(401, "Code expired — send /weblogin again")
    get_client().table("web_login_codes").update({"used": True}).eq("code", code).execute()
    _fails.pop(ip, None)  # success clears the counter
    uid = int(row["user_id"])
    response.set_cookie(
        "session", _make_token(uid),
        httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_TTL,
    )
    return {"ok": True, "uid": uid}


@app.get("/api/me")
def me(uid: int = Depends(get_current_uid)):
    return {"uid": uid}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


# --- task routes (scoped to the logged-in user) ------------------------------

def _order_active(active: list[dict]) -> list[dict]:
    """Manual order (sort_order) wins; ties / unset fall back to due-time then
    creation order. Mirrors the web UI's mental model: a user-dragged order
    overrides the due-based sort, but unordered tasks still sort by due."""
    def due_ts(t: dict):
        d = t.get("due")
        if not d:
            return float("inf")
        try:
            return datetime.fromisoformat(str(d)).timestamp()
        except Exception:
            return float("inf")

    has_manual = any(t.get("ordering") is not None for t in active)
    if not has_manual:
        return sorted(active, key=due_ts)
    # Manually-ordered tasks first (by sort_order), then the rest by due time.
    manual = sorted((t for t in active if t.get("ordering") is not None),
                    key=lambda t: t["ordering"])
    rest = sorted((t for t in active if t.get("ordering") is None), key=due_ts)
    return manual + rest


@app.get("/api/tasks")
def list_all(uid: int = Depends(get_current_uid)):
    active = _order_active(_visible(tasks_svc.list_tasks(uid, status="active")))
    completed = _visible(tasks_svc.list_tasks(uid, status="completed"))
    return {"active": active, "completed": completed}


@app.post("/api/tasks")
def add(body: NewTask, uid: int = Depends(get_current_uid)):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Title is required")
    row = tasks_svc.create_task(uid, title, "task")
    if body.due and body.due.strip():
        tasks_svc.update_task(row["id"], next_reminder_at=body.due.strip(), has_custom_time=True)
        row["next_reminder_at"] = body.due.strip()
    return _shape(row)


@app.patch("/api/tasks/{task_id}")
def patch(task_id: str, body: TaskPatch, uid: int = Depends(get_current_uid)):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != uid:
        raise HTTPException(404, "Task not found")
    fields = {}
    if body.status in ("active", "completed"):
        fields["status"] = body.status
    if body.title is not None and body.title.strip():
        fields["title"] = body.title.strip()
    if body.due is not None:
        if body.due.strip():
            fields["next_reminder_at"] = body.due.strip()
            fields["has_custom_time"] = True
        else:
            fields["next_reminder_at"] = None  # unschedule
    if not fields:
        raise HTTPException(400, "Nothing to update")
    tasks_svc.update_task(task_id, **fields)
    return _shape({**task, **fields})


@app.post("/api/tasks/{task_id}/complete")
def complete(task_id: str, uid: int = Depends(get_current_uid)):
    """Complete a task the way the bot does (bot.py done-handler):
    log the activity + bump the streak for any type, then —
      • habit  → mark_done(): advance the next reminder, task STAYS active
      • else   → status=completed: one-off task closes and leaves the list.
    Returns the reshaped task so the client can reconcile (a habit comes back
    with its new due time and status still 'active')."""
    from datetime import date
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != uid:
        raise HTTPException(404, "Task not found")

    analytics_svc.log_activity(uid, "habit", note=task.get("title", ""))
    settings_svc.update_streak(uid, date.today())

    if task.get("task_type") == "habit":
        tasks_svc.mark_done(task_id)
        # re-read so the response carries the advanced next_reminder_at
        return _shape(tasks_svc.get_task(task_id) or task)
    tasks_svc.update_task(task_id, status="completed")
    return _shape({**task, "status": "completed"})


@app.post("/api/tasks/reorder")
def reorder(body: ReorderBody, uid: int = Depends(get_current_uid)):
    """Persist a manual top-to-bottom order for active tasks. Only ids the user
    owns are written; sort_order is the index in the given list."""
    owned = {t["id"] for t in tasks_svc.list_tasks(uid, status="active")}
    for idx, tid in enumerate(body.ids):
        if tid in owned:
            tasks_svc.update_task(tid, sort_order=idx)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
def remove(task_id: str, uid: int = Depends(get_current_uid)):
    task = tasks_svc.get_task(task_id)
    if not task or task.get("user_id") != uid:
        raise HTTPException(404, "Task not found")
    tasks_svc.delete_task(task_id)
    return {"ok": True}


@app.get("/api/stats")
def stats(uid: int = Depends(get_current_uid)):
    from datetime import date, timedelta
    c = get_client()

    srow = c.table("settings").select("streak").eq("user_id", uid).limit(1).execute().data
    streak = (srow[0].get("streak") if srow else 0) or 0

    since = (date.today() - timedelta(days=6)).isoformat()
    done = (c.table("activity_log").select("id", count="exact").eq("user_id", uid)
            .in_("event_type", ["habit", "study", "milestone"]).gte("event_date", since).execute().count) or 0
    skips = (c.table("task_skips").select("id", count="exact").eq("user_id", uid)
             .gte("skipped_at", since + "T00:00:00+00:00").execute().count) or 0
    rate = round(100 * done / (done + skips)) if (done + skips) else 0
    cleared = (c.table("tasks").select("id", count="exact").eq("user_id", uid)
               .eq("status", "completed").execute().count) or 0
    return {"streak": int(streak), "week_done": done, "week_rate": rate, "cleared": cleared}


@app.get("/api/activity")
def activity(uid: int = Depends(get_current_uid), days: int = 21):
    from datetime import date, datetime as _dt, timedelta, timezone
    ist = timezone(timedelta(hours=5, minutes=30))  # IST, no DST
    c = get_client()
    days = max(7, min(days, 60))
    since = (date.today() - timedelta(days=days - 1)).isoformat()

    done_rows = (c.table("activity_log").select("event_date").eq("user_id", uid)
                 .in_("event_type", ["habit", "study", "milestone"]).gte("event_date", since).execute().data) or []
    skip_rows = (c.table("task_skips").select("skipped_at").eq("user_id", uid)
                 .gte("skipped_at", since + "T00:00:00+00:00").execute().data) or []

    done_by, skip_by = {}, {}
    for r in done_rows:
        d = str(r.get("event_date"))
        done_by[d] = done_by.get(d, 0) + 1
    for r in skip_rows:
        try:
            d = _dt.fromisoformat(r["skipped_at"]).astimezone(ist).date().isoformat()
        except Exception:
            continue
        skip_by[d] = skip_by.get(d, 0) + 1

    out = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        out.append({"date": d, "done": done_by.get(d, 0), "skipped": skip_by.get(d, 0)})
    return {"days": out}


@app.get("/api/health")
def health():
    return {"ok": True}


# --- serve the built frontend (single-service deploy) ------------------------
_STATIC_CANDIDATES = [_HERE / "static", _HERE.parents[0] / "ui" / "dist"]
STATIC_DIR = next((c for c in _STATIC_CANDIDATES if (c / "index.html").exists()), None)

if STATIC_DIR is not None:
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    def _spa(path: str):
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
