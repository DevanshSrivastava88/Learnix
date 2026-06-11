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

    # "in X hours" / "in X minutes" / bare "in X" (assume minutes)
    m = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s*(hour|hr|hours|min|mins|minute|minutes)?(?!\w)", text)
    if m:
        val = float(m.group(1))
        unit = m.group(2) or "min"  # default to minutes if no unit given
        delta = timedelta(hours=val) if "h" in unit else timedelta(minutes=val)
        return (now_ist + delta).astimezone(timezone.utc)

    # "at 6 20" / "at 6:20" / "at 3pm" / "by 6pm" anywhere in sentence
    # Also handles space-separated minutes: "at 6 20" → 6:20
    m = re.search(r"\b(?:at|by)\s+(\d{1,2})(?::(\d{2})|\s+(\d{2}))?\s*(am|pm)?(?!\d)", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or m.group(3) or 0)
        meridiem = m.group(4)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and 1 <= hour <= 12:
            # pick nearest future: try both am and pm, take closest
            am_hour = hour if hour != 12 else 0
            pm_hour = hour + 12 if hour != 12 else 12
            am_c = now_ist.replace(hour=am_hour, minute=minute, second=0, microsecond=0)
            pm_c = now_ist.replace(hour=pm_hour, minute=minute, second=0, microsecond=0)
            future = [c for c in (am_c, pm_c) if c > now_ist]
            if future:
                candidate = min(future)
            else:
                candidate = am_c + timedelta(days=1)
            return candidate.astimezone(timezone.utc)
        candidate = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_ist:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    # "3pm" / "3:30pm" / "15:00" (bare, whole string)
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and 1 <= hour <= 12:
            am_hour = hour if hour != 12 else 0
            pm_hour = hour + 12 if hour != 12 else 12
            am_c = now_ist.replace(hour=am_hour, minute=minute, second=0, microsecond=0)
            pm_c = now_ist.replace(hour=pm_hour, minute=minute, second=0, microsecond=0)
            future = [c for c in (am_c, pm_c) if c > now_ist]
            if future:
                return min(future).astimezone(timezone.utc)
            return (am_c + timedelta(days=1)).astimezone(timezone.utc)
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
        tomorrow = now_ist + timedelta(days=1)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and 1 <= hour <= 12:
            # nearest-future on tomorrow — pick am unless pm is sooner (it never is for tomorrow)
            # default to 9am-style assumption: if hour < 12 ambiguous, assume morning for "tomorrow"
            # (tomorrow morning is more natural default than tomorrow night)
            if hour < 9:
                hour += 12  # "tomorrow 6" → 6pm (evening makes more sense)
            # else keep as-is (tomorrow 9 → 9am, tomorrow 10 → 10am)
        candidate = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    return None
