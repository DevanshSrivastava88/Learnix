"""
skip_time_parser.py — Parse natural-language time expressions into UTC datetimes.
Handles: "3pm", "in 2 hours", "in 30 minutes", "10:30", "tomorrow 9am"
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

IST = pytz.timezone("Asia/Kolkata")


def parse_time_expression(text: str) -> Optional[datetime]:
    """
    Returns UTC datetime or None if unparseable.
    All times assumed IST (Asia/Kolkata).
    """
    text = text.strip().lower()
    now_ist = datetime.now(IST)

    # "in X hours" / "in X minutes"
    m = re.match(r"in\s+(\d+(?:\.\d+)?)\s*(hour|hr|hours|min|mins|minute|minutes)", text)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        delta = timedelta(hours=val) if "h" in unit else timedelta(minutes=val)
        return (now_ist + delta).astimezone(timezone.utc)

    # "3pm" / "3:30pm" / "15:00"
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        candidate = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_ist:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    # "tomorrow Xam/pm"
    m = re.match(r"tomorrow\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        tomorrow = now_ist + timedelta(days=1)
        candidate = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    return None
