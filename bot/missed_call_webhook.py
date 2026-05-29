"""
Twilio missed-call webhook → Telegram notification.

Required env vars:
  TELEGRAM_BOT_TOKEN  — same token as the Learnix bot
  TWILIO_AUTH_TOKEN   — from Twilio console (validates webhook signature)

Optional:
  TELEGRAM_CHAT_ID    — fallback if no users have /twilio on yet
  PORT                — Flask port (default 5050)
"""

import os
import hmac
import hashlib
import base64
from datetime import datetime

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


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
