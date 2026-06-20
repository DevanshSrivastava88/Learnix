"""Live: 'delete my X goal' / 'pause my X goal' by free text actually act on the matched goal."""
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
    print(f">>> {msg!r}\n    {r[:160]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # make two goals to disambiguate
    await send(c, "i want to learn spanish", wait=4)
    await send(c, "easy", wait=4)
    await send(c, "-", wait=14)  # no deadline → plan still built (one topic/day)

    # pause it by free text
    r1 = await send(c, "pause my spanish goal")
    ok1 = "paused" in r1.lower() and "spanish" in r1.lower()

    # delete it by free text → inline confirm → yes
    r2 = await send(c, "delete my spanish goal")
    ok2 = "delete" in r2.lower() and "spanish" in r2.lower() and ("yes" in r2.lower() or "confirm" in r2.lower())
    r3 = await send(c, "yes")
    ok3 = "deleted" in r3.lower() or "gone" in r3.lower()

    print("1 pause by text:", "PASS" if ok1 else f"FAIL → {r1[:140]}")
    print("2 delete asks confirm:", "PASS" if ok2 else f"FAIL → {r2[:140]}")
    print("3 confirm deletes:", "PASS" if ok3 else f"FAIL → {r3[:140]}")

    # ensure gone
    r4 = await send(c, "show my goals", wait=4)
    print("goals after:", r4[:120])
    await c.disconnect()

asyncio.run(main())
