"""Test time inputs for pending_time_for flow. Uses one-time reminders (not habits)."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"

async def reply(client, sent_id, timeout=30):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"

async def test_time(c, label, task_phrase, time_input):
    """Add a one-time reminder (should always be unscheduled), then set time."""
    s = await c.send_message(BOT, task_phrase)
    r1 = await reply(c, s.id)
    print(f"  setup reply: {r1!r}")
    if "Want to set a time" not in (r1 or ""):
        print(f"  [SKIP] didn't get time prompt — got: {r1!r}")
        return
    await asyncio.sleep(2)
    s2 = await c.send_message(BOT, time_input)
    r2 = await reply(c, s2.id)
    ok = "Set!" in (r2 or "") or ("remind" in (r2 or "").lower() and "in" in (r2 or "").lower())
    print(f"[{'PASS' if ok else 'FAIL'}] {label!r}: {r2!r}")
    await asyncio.sleep(3)

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    print("--- Time input tests ---")

    cases = [
        ("1 hr",       "remind me to call dentist",   "1 hr"),
        ("in 30 mins", "remind me to take meds",      "in 30 mins"),
        ("30m",        "remind me to check mail",     "30m"),
        ("next hour",  "remind me to drink water",    "next hour"),
        ("2 hours",    "remind me to send that email","2 hours"),
        ("8pm",        "remind me to call dad",       "8pm"),
    ]
    for label, task, time_input in cases:
        print(f"\nTesting: {label!r}")
        await test_time(c, label, task, time_input)

    await c.disconnect()

asyncio.run(main())
