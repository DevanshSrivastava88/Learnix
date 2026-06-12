"""Verify: multi-task in one message, pause→resume free text."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"

async def replies(client, sent_id, want=1, timeout=30):
    got, dl = [], asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl and len(got) < want:
        for m in reversed(await client.get_messages(BOT, limit=8)):
            if m.id > sent_id and not m.out and (m.text or "") not in got:
                got.append(m.text or "")
        await asyncio.sleep(1)
    return got

async def send(c, msg, want=1, wait=8):
    s = await c.send_message(BOT, msg)
    rs = await replies(c, s.id, want)
    for r in rs:
        print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return rs

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # 1. two tasks, one message
    rs = await send(c, "remind me to call ravi in 1 hour and pick up laundry in 2 hours", want=2, wait=10)
    joined = " | ".join(rs).lower()
    ok1 = "ravi" in joined and "laundry" in joined and len(rs) >= 2

    # 2. pause then free-text resume
    await send(c, "add habit pushups")
    await send(c, "no")
    await send(c, "pause pushups")
    rs2 = await send(c, "resume pushups")
    ok2 = any("active again" in r.lower() or "back on" in r.lower() for r in rs2)

    print("1 multi-task:", "PASS" if ok1 else f"FAIL → {joined[:200]}")
    print("2 resume free-text:", "PASS" if ok2 else f"FAIL → {rs2}")

    for t in ("call ravi", "pick up laundry", "pushups"):
        await send(c, f"delete {t}", wait=4)
    await c.disconnect()

asyncio.run(main())
