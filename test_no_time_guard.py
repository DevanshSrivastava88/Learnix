"""Verify: task without time never gets phantom reminder; activity verb kept in title."""
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

    # No time given — must ask, never set a phantom reminder (run 3x: hallucination was flaky)
    results = []
    for word in ("fart", "burp", "yawn"):
        r = await send(c, f"add {word}")
        ok = "Want to set a time" in r
        results.append((word, ok, r[:80]))
        await send(c, "no")
        await send(c, f"delete {word}")
    # Activity verb kept in title
    r2 = await send(c, "add wash dishes")
    verb_ok = "Wash Dishes" in r2
    await send(c, "no")
    await send(c, "delete wash dishes")

    for word, ok, r in results:
        print(f"{word}: {'PASS' if ok else 'FAIL → ' + r}")
    print(f"verb kept: {'PASS' if verb_ok else 'FAIL → ' + r2[:80]}")

    await c.disconnect()

asyncio.run(main())
