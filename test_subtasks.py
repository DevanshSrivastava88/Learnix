"""Verify subtasks: AI breakdown with review, revise, manual add, indented list, done, cascade delete. Plus weekday retest."""
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

async def send(c, msg, wait=8):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # 1. AI breakdown proposes with review (nothing created yet)
    r1 = await send(c, "break down paint the fence", wait=10)
    if "plan for" not in r1.lower():
        r1 = await reply(c, 0)  # second message may carry the plan
    ok1 = "yes" in r1.lower() and "1." in r1

    # 2. revise: add a step
    r2 = await send(c, "add buy brushes as first step", wait=10)
    ok2 = "buy brushes" in r2.lower() or "brushes" in r2.lower()

    # 3. confirm
    r3 = await send(c, "yes")
    ok3 = "subtask" in r3.lower() and "added" in r3.lower()

    # 4. manual single subtask
    r4 = await send(c, "add subtask clean up site to paint the fence")
    ok4 = "clean up site" in r4.lower() and "paint the fence" in r4.lower()

    # 5. list shows parent + indented dashes
    r5 = await send(c, "list")
    print("LIST:\n", r5, "\n")
    ok5 = "Paint The Fence" in r5 or "Paint the Fence" in r5
    ok5 = ok5 and "- " in r5 and "clean up site" in r5.lower()

    # 6. done one subtask
    r6 = await send(c, "done buy brushes")
    ok6 = "✅" in r6 and "remind you again" not in r6.lower()

    # 7. weekday retest (deterministic offset now): sunday
    r7 = await send(c, "remind me to water plants on sunday")
    ok7 = "sunday" in r7.lower()
    r8 = await send(c, "8am")
    ok8 = "8:00 AM" in r8 and ("Sun" in r8 or "14" in r8)

    # 8. cascade delete parent
    r9 = await send(c, "delete paint the fence")
    r10 = await send(c, "list")
    ok9 = "paint" not in r10.lower()

    for n, (name, ok, ev) in enumerate([
        ("breakdown review", ok1, r1), ("revise adds step", ok2, r2), ("confirm creates", ok3, r3),
        ("manual subtask", ok4, r4), ("indented list", ok5, r5), ("done subtask", ok6, r6),
        ("sunday named", ok7, r7), ("8am lands sunday", ok8, r8), ("cascade delete", ok9, r10),
    ], 1):
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {ev[:150]}"))

    await send(c, "delete water plants")
    await c.disconnect()

asyncio.run(main())
