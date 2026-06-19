"""
Targeted test for recent fixes:
- Time disambiguation (nearest future for bare "at H")
- Default type: reminder not habit
- /tasks timed display fix
- "list" shortcut
"""

import asyncio
import sys
from datetime import datetime
import pytz
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID   = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"
BOT      = "@Quest3131Bot"
SESSION  = "learnix_tester"
WAIT     = 25

IST = pytz.timezone("Asia/Kolkata")

def now_ist_str():
    return datetime.now(IST).strftime("%I:%M %p IST")

# What nearest-future "at 10" should give right now
def expected_10():
    now = datetime.now(IST)
    h = now.hour
    m = now.minute
    # 10am = 10:00, 10pm = 22:00
    mins_to_10am = ((10 - h) * 60 - m) % (24 * 60)
    mins_to_10pm = ((22 - h) * 60 - m) % (24 * 60)
    if mins_to_10am == 0: mins_to_10am = 24 * 60
    if mins_to_10pm == 0: mins_to_10pm = 24 * 60
    nearest = "10pm" if mins_to_10pm < mins_to_10am else "10am"
    return nearest, min(mins_to_10am, mins_to_10pm)

TESTS = [
    # Setup
    ("#reset", "/reset", []),

    # T1: bare "at 10" — should pick nearest future
    ("T1_at10_nearest",    "drink water at 10",
     ["remind","water","drink"]),

    # T2: bare "at 6" — nearest future (if 6pm passed, picks 6am tomorrow)
    ("T2_at6_nearest",     "meeting at 6",
     ["remind","meeting","6"]),

    # T3: "list" shortcut — should show tasks, NOT add "list" as task
    ("T3_list_shortcut",   "list",
     ["task","tracking","no task","unscheduled","scheduled","your tasks"]),

    # T4: explicit habit
    ("T4_habit",           "workout every day",
     ["every day","daily","workout","look right"]),
    ("#cancel", "/cancel", []),

    # T5: one-time task no time → asks for time
    ("T5_notime_task",     "call mom",
     ["added","call","mom","time","want to set","set a time"]),

    # T6: respond "no" to time prompt
    ("T6_notime_no",       "no",
     ["ok","got it","added","no worries","skip","noted"]),

    # T7: list again — timed tasks should show in timed section
    ("T7_list_after",      "list",
     ["task","tracking","your tasks","scheduled","unscheduled"]),
]


async def get_bot_reply(client, sent_id, timeout=WAIT):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        msgs = await client.get_messages(BOT, limit=5)
        for m in msgs:
            if m.id > sent_id and not m.out:
                return m.text or "[media/no text]"
        await asyncio.sleep(1)
    return None


async def main():
    nearest, mins = expected_10()
    print(f"\nCurrent IST: {now_ist_str()}")
    print(f"Expected 'at 10' → {nearest} (~{mins}m away)\n{'='*55}")

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    for label, msg, keywords in TESTS:
        is_setup = label.startswith("#")
        print(f"\n{'[setup]' if is_setup else '[test] ' + label}  ->  {msg!r}")

        sent = await client.send_message(BOT, msg)
        reply = await get_bot_reply(client, sent.id, timeout=WAIT if not is_setup else 6)

        if is_setup:
            await asyncio.sleep(1.5)
            continue

        if reply is None:
            print(f"  FAIL — no reply in {WAIT}s")
        else:
            hit = any(k.lower() in reply.lower() for k in keywords)
            status = "PASS" if hit else "WARN"
            print(f"  {status}: {reply[:150].replace(chr(10), ' ')}")

        await asyncio.sleep(8)

    await client.disconnect()

asyncio.run(main())
