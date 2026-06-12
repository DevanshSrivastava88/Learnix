"""Full feature sweep — realistic daily-use scenarios across every feature."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
RESULTS = []

async def reply(client, sent_id, timeout=30):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=6):
            if m.id > sent_id and not m.out:
                if m.text:
                    return m.text
                if m.media:
                    return "[photo]"
        await asyncio.sleep(1)
    return "[timeout]"

async def send(c, msg, wait=8):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r[:200]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

def check(name, ok, ev=""):
    RESULTS.append((name, ok, ev))

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # --- everyday task flows ---
    r = await send(c, "remind me to call the electrician at 4pm")
    check("timed reminder 4pm", "4:00 PM" in r, r)

    r = await send(c, "add buy groceries")
    check("untimed add asks time", "time" in r.lower(), r)
    await send(c, "no")

    r = await send(c, "done buy groceries")
    check("done one-time completes", "✅" in r and "remind you again" not in r.lower(), r)

    r = await send(c, "remind me to submit the report tomorrow at 10am")
    check("tomorrow 10am", "10:00 AM tomorrow" in r, r)

    r = await send(c, "move the electrician call to 6pm")
    check("reschedule to 6pm", "6" in r and ("pm" in r.lower()), r)

    r = await send(c, "mark the electrician call as important")
    check("mark important", "important" in r.lower() or "⚡" in r, r)

    # --- habits ---
    r = await send(c, "add habit drink water every day at 9am")
    check("timed habit 9am", "9:00 AM" in r, r)

    r = await send(c, "skip drink water today")
    check("skip habit", "skip" in r.lower(), r)

    # --- views ---
    r = await send(c, "list")
    check("list renders sections", "Your tasks" in r, r)

    r = await send(c, "what's my schedule today")
    check("schedule view", "[timeout]" not in r and len(r) > 20, r)

    r = await send(c, "/graph")
    check("activity graph", r == "[photo]" or "activity" in r.lower() or "yet" in r.lower(), r)

    r = await send(c, "/skipgraph")
    check("skip graph", r == "[photo]" or "skip" in r.lower(), r)

    r = await send(c, "/settings")
    check("settings", "[timeout]" not in r and len(r) > 20, r)

    r = await send(c, "what can you do")
    check("help", "study" in r.lower() or "task" in r.lower() or "remind" in r.lower(), r)

    # --- chat ---
    r = await send(c, "im feeling lazy today man")
    check("chat empathy", "[timeout]" not in r and "task" not in r[:30].lower(), r)

    # --- study basics (pre-revamp sanity) ---
    r = await send(c, "i want to learn guitar")
    check("create goal", "guitar" in r.lower(), r)
    if "difficulty" in r.lower() or "easy" in r.lower():
        r = await send(c, "easy")
        check("goal difficulty flow", "[timeout]" not in r, r)

    r = await send(c, "show my goals")
    check("show goals", "guitar" in r.lower(), r)

    # --- cleanup ---
    for t in ("the electrician call", "submit the report", "drink water habit"):
        await send(c, f"delete {t}", wait=4)
    r = await send(c, "delete my guitar goal")
    check("delete goal", "guitar" in r.lower(), r)
    r = await send(c, "list")
    print("FINAL LIST:\n", r)

    print("\n=== RESULTS ===")
    for name, ok, ev in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {ev[:150]}"))

    await c.disconnect()

asyncio.run(main())
