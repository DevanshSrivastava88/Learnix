"""Retest the 3 fixed bugs: inline habit time, done preserves clock, delete paused."""
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

    # 1. inline habit time — created immediately at 9pm, no re-ask
    r1 = await send(c, "add habit stretching at 9pm")
    ok1 = "9:00 PM" in r1 and "specific time" not in r1.lower()

    # 2. done preserves 9pm clock — list should show tomorrow 9pm
    r2 = await send(c, "done stretching")
    r3 = await send(c, "list")
    ok2 = "9pm → 🔁 Stretching" in r3 or "9pm → 🔁 stretching" in r3.lower().replace("9pm", "9pm")
    ok2 = "stretching" in r3.lower() and "9pm" in r3.lower().split("stretching")[0].split("\n")[-1]

    # 3. delete paused task (meditation was left paused by previous suite)
    r4 = await send(c, "delete meditation")
    ok3 = "meditation" in r4.lower() and ("gone" in r4.lower() or "deleted" in r4.lower())

    await send(c, "delete stretching")

    print("1 inline habit time:", "PASS" if ok1 else f"FAIL → {r1[:120]}")
    print("2 done keeps 9pm:", "PASS" if ok2 else f"FAIL → {r3[:300]}")
    print("3 delete paused:", "PASS" if ok3 else f"FAIL → {r4[:120]}")

    await c.disconnect()

asyncio.run(main())
