"""Verify weekday dates: 'on monday at 5pm' and bare 'friday' follow-up."""
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

    # Today is Fri 12 Jun 2026 → Monday = 15 Jun
    r1 = await send(c, "remind me to pay rent on monday at 5pm")
    ok1 = "5:00 PM" in r1 and ("Mon" in r1 or "15" in r1)

    # Weekday without time — date should be remembered through follow-up
    r2 = await send(c, "remind me to water plants on sunday")
    ok2 = "sunday" in r2.lower() and "time" in r2.lower()
    r3 = await send(c, "8am")
    ok3 = "8:00 AM" in r3 and ("Sun" in r3 or "14" in r3)

    r4 = await send(c, "list")
    print("LIST:\n", r4, "\n")
    ok4 = ("Mon 15 Jun" in r4) and ("Sun 14 Jun" in r4)

    print("1 monday 5pm:", "PASS" if ok1 else f"FAIL → {r1[:120]}")
    print("2 sunday remembered:", "PASS" if ok2 else f"FAIL → {r2[:120]}")
    print("3 8am lands sunday:", "PASS" if ok3 else f"FAIL → {r3[:120]}")
    print("4 list day labels:", "PASS" if ok4 else f"FAIL → {r4[:300]}")

    await send(c, "delete pay rent")
    await send(c, "delete water plants")
    await c.disconnect()

asyncio.run(main())
