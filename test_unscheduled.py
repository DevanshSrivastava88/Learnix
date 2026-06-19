import asyncio, sys
from telethon import TelegramClient
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID, API_HASH, BOT, SESSION, WAIT = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester", 20

async def reply(client, sent_id):
    dl = asyncio.get_event_loop().time() + WAIT
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return None

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    steps = ["/reset", "call mom", "no", "list"]
    for msg in steps:
        s = await c.send_message(BOT, msg)
        r = await reply(c, s.id)
        print(f"\n>>> {msg!r}\n{r}")
        await asyncio.sleep(6)
    await c.disconnect()

asyncio.run(main())
