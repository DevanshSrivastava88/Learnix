"""Live: guided session — study a planned goal, get day-X/N header + lesson + quiz, complete a topic."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"

async def reply(client, sent_id, timeout=45):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=6):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"

async def latest(client, n=6):
    return [m.text for m in await client.get_messages(BOT, limit=n) if not m.out and m.text]

async def send(c, msg, wait=10):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r[:160]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # set up a planned goal
    await send(c, "i want to learn chess", wait=4)
    await send(c, "easy", wait=4)
    await send(c, "2026-07-13", wait=16)

    # start guided session
    r1 = await send(c, "study chess", wait=14)
    ok_header = "day" in r1.lower() and ("today" in r1.lower() or "chess" in r1.lower())
    # after a beat, the lesson + quiz Q1 should have arrived
    recent = " ||| ".join(await latest(c, 6)).lower()
    ok_lesson = "q1" in recent or "quiz" in recent

    print("1 guided header:", "PASS" if ok_header else f"FAIL → {r1[:160]}")
    print("2 lesson+quiz started:", "PASS" if ok_lesson else f"FAIL → {recent[:200]}")

    # exit quiz cleanly
    await send(c, "/cancel", wait=4)
    await c.disconnect()

asyncio.run(main())
