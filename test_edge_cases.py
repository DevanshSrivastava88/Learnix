"""Stress suite: habit variants, exact times, day offsets, actions."""
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

RESULTS = []
def check(name, ok, evidence):
    RESULTS.append((name, ok, evidence))

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # 1. Habit with inline time — should NOT re-ask for time
    r = await send(c, "add habit reading at 9pm")
    check("habit inline time", "9" in r and "any specific time" not in r.lower(), r[:120])
    if "any specific time" in r.lower() or "specific time" in r.lower():
        await send(c, "9pm")

    # 2. Recurrence phrase variant
    r = await send(c, "track meditation every morning")
    check("every morning habit", "meditation" in r.lower(), r[:120])
    if "specific time" in r.lower():
        await send(c, "no")

    # 3. Exact minutes
    r = await send(c, "remind me to call dad at 6:45 pm")
    check("exact 6:45pm", "6:45 PM" in r, r[:120])

    # 4. Day after tomorrow + time
    r = await send(c, "add pay rent day after tomorrow at 5pm")
    check("day after tomorrow", "5:00 PM" in r and ("Sat" in r or "tomorrow" not in r), r[:120])

    # 5. Relative leading
    r = await send(c, "remind me in 90 mins to take a break")
    check("in 90 mins", "1h 30m" in r or "90 min" in r, r[:120])

    # 6. Reschedule
    r = await send(c, "move call dad to 7:15 pm")
    check("reschedule 7:15pm", "7:15" in r.lower() or "07:15" in r, r[:120])

    # 7. Mark important
    r = await send(c, "mark call dad important")
    check("mark important", "important" in r.lower() or "⚡" in r, r[:120])

    # 8. Done on habit
    r = await send(c, "done reading")
    check("done habit", "done" in r.lower() or "✅" in r or "nice" in r.lower(), r[:120])

    # 9. Pause
    r = await send(c, "pause meditation")
    check("pause", "pause" in r.lower(), r[:120])

    # 10. List sections sanity
    r = await send(c, "list")
    check("list renders", "Your tasks" in r, r[:300])
    print("FULL LIST:\n", r, "\n")

    # cleanup
    for t in ("call dad", "take a break", "pay rent", "reading", "meditation"):
        await send(c, f"delete {t}", wait=5)

    print("\n=== RESULTS ===")
    for name, ok, ev in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {ev}"))

    await c.disconnect()

asyncio.run(main())
