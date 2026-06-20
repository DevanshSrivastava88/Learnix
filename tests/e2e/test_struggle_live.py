"""Live test: reactive struggle-support uses the new context engine.

Sends a struggle message to the deployed bot and checks the reply:
  - validates + attaches the GUARANTEED concrete offer (deterministic)
  - references real data (streak / task name / win) — printed for eyeball check
"""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"


async def reply(client, sent_id, timeout=35):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"


async def send(c, msg, wait=6):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""


async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    r = await send(c, "honestly i keep failing at everything lately, feeling like giving up")

    low = r.lower()
    has_offer = ("pause" in low or "lighten the load" in low or "scale" in low)
    has_tomorrow = "tomorrow" in low
    not_empty = len(r.strip()) > 0 and r != "[timeout]"

    print("=" * 60)
    print("OFFER present   :", has_offer)
    print("mentions tomorrow:", has_tomorrow)
    print("got a reply     :", not_empty)
    print("RESULT:", "PASS" if (has_offer and not_empty) else "CHECK MANUALLY")
    print("=" * 60)

    await c.disconnect()

asyncio.run(main())
