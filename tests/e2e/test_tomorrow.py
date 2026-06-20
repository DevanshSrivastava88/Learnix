"""Verify: 'tomorrow' date sticks through the time follow-up, list shows Upcoming section."""
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

    # 1. tomorrow, no time → ask time, remember the date
    r1 = await send(c, "remind me to floss tomorrow")
    ok1 = "tomorrow" in r1.lower() and "time" in r1.lower()
    # 2. answer with time → lands tomorrow 9am
    r2 = await send(c, "9am")
    ok2 = "9:00 AM tomorrow" in r2
    # 3. tomorrow + inline time
    r3 = await send(c, "add gym tomorrow at 7 am")
    ok3 = "7:00 AM tomorrow" in r3
    # 4. list shows Upcoming section
    r4 = await send(c, "list")
    ok4 = "Upcoming" in r4 and "tomorrow" in r4.lower()

    print("1 date remembered:", "PASS" if ok1 else f"FAIL → {r1[:100]}")
    print("2 time lands tomorrow:", "PASS" if ok2 else f"FAIL → {r2[:100]}")
    print("3 inline tomorrow+time:", "PASS" if ok3 else f"FAIL → {r3[:100]}")
    print("4 Upcoming section:", "PASS" if ok4 else f"FAIL → {r4[:300]}")

    await send(c, "delete floss")
    await send(c, "delete gym")

    await c.disconnect()

asyncio.run(main())
