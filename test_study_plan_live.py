"""Live test: goal with deadline -> auto topics + dated plan; /progress shows on-track."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"

async def reply(client, sent_id, timeout=40):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"

async def send(c, msg, wait=9):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # Create a goal with a deadline → should auto-generate topics + dated plan
    r1 = await send(c, "i want to learn french", wait=4)
    ok_diff = "difficulty" in r1.lower()
    r2 = await send(c, "easy", wait=4)
    await send(c, "2026-07-13", wait=15)  # "Building..." then the plan as a 2nd message
    # grab the most recent bot message (the actual plan)
    msgs = await c.get_messages(BOT, limit=3)
    r3 = next((m.text for m in msgs if not m.out and "study plan" in (m.text or "").lower()), "")
    print("PLAN MSG:\n", r3, "\n")
    ok_plan = "study plan" in r3.lower() and ("today" in r3.lower() or "jul" in r3.lower())
    ok_topics = r3.count("\n") >= 4  # several topics listed

    # Progress shows day X/N on-track
    r4 = await send(c, "how am i doing with french", wait=6)
    ok_prog = "day" in r4.lower() and "on track" in r4.lower()  # day 1 must read on-track now

    print("1 difficulty prompt:", "PASS" if ok_diff else f"FAIL → {r1[:100]}")
    print("2 dated plan built:", "PASS" if ok_plan else f"FAIL → {r3[:200]}")
    print("3 plan has topics:", "PASS" if ok_topics else f"FAIL → {r3[:200]}")
    print("4 progress on-track:", "PASS" if ok_prog else f"FAIL → {r4[:200]}")

    await send(c, "delete my french goal", wait=4)
    await c.disconnect()

asyncio.run(main())
