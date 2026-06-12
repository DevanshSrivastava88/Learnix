"""Focused test: 'set X to [time]' reschedules existing task to exact time (no duplicate)."""
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

    # 1. Reschedule existing unscheduled task to exact absolute time
    r1 = await send(c, "set drink to 9:30 pm")
    ok1 = "9:30" in r1 and "drink" in r1.lower()
    # 2. New task with absolute time — must be exact, not LLM-rounded
    r2 = await send(c, "remind me to take vitamins at 8 pm")
    ok2 = "8:00 PM" in r2 or "8 PM" in r2.replace(":00", "")
    r3 = await send(c, "list")
    # vitamins should show at exactly 08:00pm
    ok3 = "8:00pm" in r3.lower().replace(" ", "") and r3.lower().count("drink water") <= 1
    print("R1 reschedule exact:", "PASS" if ok1 else f"FAIL → {r1[:100]}")
    print("R2 new task exact:", "PASS" if ok2 else f"FAIL → {r2[:100]}")
    print("R3 list:", "PASS" if ok3 else f"CHECK → {r3[:300]}")

    # cleanup: delete vitamins test task
    await send(c, "delete take vitamins")

    await c.disconnect()

asyncio.run(main())
