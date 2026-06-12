"""Verify habit logic: type word stripped, no-time = no reminder, list shows habit in Upcoming + Unscheduled."""
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

async def send(c, msg, wait=8):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # habit type word stripped from title
    r1 = await send(c, "add habit journaling daily")
    ok1 = "Journaling" in r1 and "Habit" not in r1.replace("Habits", "")
    if "specific time" in r1.lower() or "time" in r1.lower():
        await send(c, "no")
    r2 = await send(c, "list")
    low = r2.lower()
    # existing no-time habit Gym: in Upcoming as tomorrow + in Unscheduled with every day
    ok2 = "tomorrow → 🔁 gym" in low or ("upcoming" in low and "🔁 gym" in low)
    ok3 = "🔁 gym — every day" in low
    # journaling habit also reminder-less → unscheduled, no Today entry with a time
    ok4 = "journaling" in low and "→ 🔁 journaling" not in low.split("upcoming")[0]

    print("1 title stripped:", "PASS" if ok1 else f"FAIL → {r1[:100]}")
    print("2 habit in Upcoming:", "PASS" if ok2 else f"FAIL → {r2[:300]}")
    print("3 habit in Unscheduled w/ freq:", "PASS" if ok3 else f"FAIL → {r2[:300]}")
    print("4 no phantom time today:", "PASS" if ok4 else f"FAIL → {r2[:300]}")

    await send(c, "delete journaling")
    await c.disconnect()

asyncio.run(main())
