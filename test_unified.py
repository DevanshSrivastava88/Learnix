"""Live test of the unified understand_message flow — one scenario at a time."""
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

async def send(c, msg, wait=6):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    print("=== 1. inline time: task created + scheduled in ONE message ===")
    r = await send(c, "remind me to call mom in 4 hours")
    print("PASS" if "4h" in r or "3h 59" in r or "240" in r else "FAIL", "- inline time\n")

    print("=== 2. unscheduled + bare time follow-up ===")
    r = await send(c, "add buy groceries")
    if "Want to set a time" in r:
        r2 = await send(c, "1 hr")
        print("PASS" if "59 min" in r2 or "1h" in r2 or "60 min" in r2 else "FAIL", "- bare '1 hr'\n")
    else:
        print("FAIL - no time prompt:", r[:80], "\n")

    print("=== 3. cancel it (context) ===")
    r = await send(c, "add stretch break")
    if "Want to set a time" in r:
        await send(c, "no")
    r3 = await send(c, "cancel it")
    print("PASS" if ("stretch" in r3.lower() or "delete" in r3.lower() or "cancel" in r3.lower() or "removed" in r3.lower() or "gone" in r3.lower()) else "CHECK", "- cancel it →", r3[:100], "\n")

    print("=== 4. gibberish must NOT create a task ===")
    r4 = await send(c, "mo")
    print("PASS" if "Added" not in r4 else "FAIL", "- gibberish 'mo' →", r4[:80], "\n")

    print("=== 5. task list sanity ===")
    r5 = await send(c, "show my tasks")
    print(r5)

    await c.disconnect()

asyncio.run(main())
