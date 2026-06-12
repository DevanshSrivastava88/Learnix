"""Focused test: bare 'cancel' (no pronoun) deletes last-discussed task."""
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

    r = await send(c, "add call shreyash test")
    if "Want to set a time" in r:
        await send(c, "1h")
    r2 = await send(c, "cancel")
    r3 = await send(c, "list")
    gone = "shreyash test" not in r3.lower()
    print("CANCEL REPLY:", r2[:120])
    print("LIST:", r3[:200])
    print("RESULT:", "PASS" if gone and "shreyash" in r2.lower() else "FAIL")

    await c.disconnect()

asyncio.run(main())
