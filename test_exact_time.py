"""Verify absolute-time task stores exact clock time (no 1-min drift)."""
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

    r1 = await send(c, "remind me to take vitamins at 8 pm")
    r2 = await send(c, "list")
    ok = "8:00pm" in r2.lower().replace(" ", "") or "8pm →" in r2.lower()
    print("RESULT:", "PASS" if ok and "8:00 PM" in r1 else f"FAIL → {r2[:200]}")
    await send(c, "delete take vitamins")

    await c.disconnect()

asyncio.run(main())
