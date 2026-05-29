"""
run_all.py — Start both the Learnix bot and the Twilio missed-call webhook.

Usage:
    python run_all.py

Flask webhook runs in a daemon thread (port 5050).
Bot runs in the main thread via run_polling.
"""

import os
import threading
from dotenv import load_dotenv

load_dotenv()


def _start_flask() -> None:
    from missed_call_webhook import app as flask_app
    port = int(os.environ.get("PORT", 5050))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)


def main() -> None:
    flask_thread = threading.Thread(target=_start_flask, daemon=True, name="flask-webhook")
    flask_thread.start()
    print(f"[run_all] Flask webhook started on port {os.environ.get('PORT', 5050)}")

    from bot import main as run_bot
    run_bot()


if __name__ == "__main__":
    main()
