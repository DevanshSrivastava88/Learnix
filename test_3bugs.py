"""Retest the 3 sweep bugs: mark important, skip one-time task (no crash), learn X -> goal."""
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

    # Bug 1: mark X as important — must flag existing, not create "Mark X"
    await send(c, "remind me to call the plumber at 3pm")
    r1 = await send(c, "mark the plumber call as important")
    ok1 = "important" in r1.lower() and "got it:" not in r1.lower() and "every day" not in r1.lower()

    # Bug 2: skip a one-time task — must NOT crash
    await send(c, "add water the garden")
    await send(c, "no")
    r2 = await send(c, "skip water the garden today")
    ok2 = "broke" not in r2.lower() and ("skip" in r2.lower())

    # Bug 3: "I want to learn X" -> create_goal, not a task
    r3 = await send(c, "i want to learn spanish")
    ok3 = "goal" in r3.lower() or "difficulty" in r3.lower() or "easy" in r3.lower() or "learning" in r3.lower()
    # if it entered goal flow, back out
    if "difficulty" in r3.lower() or "easy" in r3.lower():
        await send(c, "easy")
        await send(c, "no deadline" if False else "/cancel")

    print("1 mark important flags existing:", "PASS" if ok1 else f"FAIL → {r1[:150]}")
    print("2 skip one-time no crash:", "PASS" if ok2 else f"FAIL → {r2[:150]}")
    print("3 learn X -> goal:", "PASS" if ok3 else f"FAIL → {r3[:150]}")

    # cleanup
    for t in ("the plumber call", "water the garden"):
        await send(c, f"delete {t}", wait=4)
    await send(c, "delete my spanish goal", wait=4)
    r = await send(c, "list")
    print("FINAL LIST:\n", r)

    await c.disconnect()

asyncio.run(main())
