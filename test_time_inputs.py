"""Test various time inputs for the pending_time_for flow."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"

async def reply(client, sent_id, timeout=25):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"

async def test(c, label, setup_msg, time_input):
    s = await c.send_message(BOT, setup_msg)
    await reply(c, s.id)  # consume "Added X" reply
    await asyncio.sleep(2)
    s2 = await c.send_message(BOT, time_input)
    r = await reply(c, s2.id)
    status = "PASS" if ("Set!" in (r or "") or "remind" in (r or "").lower()) else "FAIL"
    print(f"[{status}] {label!r} → {r!r}")
    await asyncio.sleep(3)

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    cases = [
        ("1 hr",        "add call mom",    "1 hr"),
        ("in 30 mins",  "add drink water", "in 30 mins"),
        ("next hour",   "add meditation",  "next hour"),
        ("8pm",         "add read book",   "8pm"),
        ("30m",         "add pushups",     "30m"),
        ("2 hours",     "add journal",     "2 hours"),
    ]

    for label, setup, time_input in cases:
        await test(c, label, setup, time_input)

    await c.disconnect()

asyncio.run(main())
