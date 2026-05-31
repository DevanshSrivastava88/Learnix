"""
Twilio missed-call webhook → Telegram notification.

Required env vars:
  TELEGRAM_BOT_TOKEN  — same token as the Learnix bot
  TWILIO_AUTH_TOKEN   — from Twilio console (validates webhook signature)

Optional:
  TELEGRAM_CHAT_ID    — fallback if no users have /twilio on yet
  SUPABASE_URL        — for call-response route to update DB
  SUPABASE_KEY        — for call-response route to update DB
  PORT                — Flask port (default 5050)
"""

import os
import hmac
import hashlib
import base64
from datetime import datetime, timezone, timedelta

import pytz
from flask import Flask, request, Response
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]

IST = pytz.timezone("Asia/Kolkata")


def _twilio_signature(auth_token: str, url: str, params: dict) -> str:
    s = url
    for key in sorted(params.keys()):
        s += key + params[key]
    mac = hmac.new(auth_token.encode(), s.encode(), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode()


def _validate_twilio(req) -> bool:
    signature = req.headers.get("X-Twilio-Signature", "")
    expected  = _twilio_signature(TWILIO_AUTH_TOKEN, req.url, req.form.to_dict())
    return hmac.compare_digest(signature, expected)


def _send_telegram(chat_id, text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as exc:
        print(f"[webhook] Telegram send failed for {chat_id}: {exc}")


def _notify_all(text: str) -> None:
    import twilio_svc
    users = twilio_svc.get_all_twilio_users()
    if not users:
        fallback = os.environ.get("TELEGRAM_CHAT_ID")
        if fallback:
            _send_telegram(fallback, text)
        else:
            print("[webhook] No twilio_enabled users and no TELEGRAM_CHAT_ID fallback.")
        return
    for row in users:
        _send_telegram(row["user_id"], text)


@app.route("/twilio/missed-call", methods=["POST"])
def missed_call():
    if not _validate_twilio(request):
        return Response("Forbidden", status=403)

    call_status = request.form.get("CallStatus", "")
    from_number = request.form.get("From", "unknown")

    if call_status not in ("no-answer", "busy", "failed"):
        return Response("", status=204)

    now_ist  = datetime.now(IST)
    time_str = now_ist.strftime("%I:%M %p").lstrip("0")  # "3:42 PM" (Windows-safe)
    date_str = now_ist.strftime("%d %b")

    status_label = {"no-answer": "no answer", "busy": "busy", "failed": "failed"}[call_status]

    message = (
        f"📞 <b>Missed call</b> from <code>{from_number}</code>\n"
        f"🕐 {time_str} on {date_str}  ({status_label})\n\n"
        f"Reply here to remind yourself to call back."
    )

    _notify_all(message)
    return Response("<Response/>", status=200, mimetype="text/xml")


def _get_supabase():
    """Return a lightweight Supabase client using the supabase-py library."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _mark_task_done_supabase(task_id: str) -> bool:
    """Mark a habit done and advance next_reminder_at by recurrence_days."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        res = sb.table("tasks").select("recurrence_days").eq("id", task_id).execute()
        if not res.data:
            return False
        recurrence = res.data[0].get("recurrence_days", 1) or 1
        next_at = (datetime.now(timezone.utc) + timedelta(days=recurrence)).isoformat()
        sb.table("tasks").update({"next_reminder_at": next_at}).eq("id", task_id).execute()
        return True
    except Exception as exc:
        print(f"[webhook] mark_task_done failed for {task_id}: {exc}")
        return False


def _skip_task_supabase(task_id: str, user_id: int) -> bool:
    """Log a skip and advance next_reminder_at by recurrence_days."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        res = sb.table("tasks").select("recurrence_days").eq("id", task_id).execute()
        if not res.data:
            return False
        recurrence = res.data[0].get("recurrence_days", 1) or 1
        next_at = (datetime.now(timezone.utc) + timedelta(days=recurrence)).isoformat()
        sb.table("tasks").update({"next_reminder_at": next_at}).eq("id", task_id).execute()
        try:
            sb.table("task_skips").insert({
                "user_id": user_id,
                "task_id": task_id,
                "note": "ivr_skip",
            }).execute()
        except Exception:
            pass  # skip log is non-critical
        return True
    except Exception as exc:
        print(f"[webhook] skip_task failed for {task_id}: {exc}")
        return False


def _get_task_title(task_id: str) -> str:
    """Return task title from Supabase, or empty string."""
    sb = _get_supabase()
    if not sb:
        return ""
    try:
        res = sb.table("tasks").select("title").eq("id", task_id).execute()
        return res.data[0].get("title", "") if res.data else ""
    except Exception:
        return ""


@app.route("/twilio/call-response", methods=["POST"])
def call_response():
    """Handle IVR digit press: 1 = done, 2 = skip."""
    digit = request.form.get("Digits", "")
    task_id = request.args.get("task_id", "")
    user_id_str = request.args.get("user_id", "")

    if not task_id or not user_id_str:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Invalid request.</Say></Response>',
            status=200,
            mimetype="text/xml",
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Invalid user.</Say></Response>',
            status=200,
            mimetype="text/xml",
        )

    title = _get_task_title(task_id) or "your task"

    if digit == "1":
        _mark_task_done_supabase(task_id)
        _send_telegram(user_id, f"✅ Great! Marked <b>{title}</b> as done via phone call. Keep it up!")
        response_say = "Awesome! Marked as done. Keep it up!"
    elif digit == "2":
        _skip_task_supabase(task_id, user_id)
        _send_telegram(user_id, f"⏭ Skipped <b>{title}</b> for now.")
        response_say = "Got it, skipped for now."
    else:
        response_say = "I'll remind you again in one hour."

    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>{response_say}</Say></Response>',
        status=200,
        mimetype="text/xml",
    )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
