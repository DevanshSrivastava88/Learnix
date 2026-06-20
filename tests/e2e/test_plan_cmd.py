"""Live: /plan and 'my plan' show the full dated schedule with status icons."""
import asyncio, os, sys
from dotenv import load_dotenv
from supabase import create_client
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv("bot/.env")
API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

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
    print(f">>> {msg!r}\n    {r[:200]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    await send(c, "i want to learn cooking", wait=4)
    await send(c, "easy", wait=4)
    await send(c, "2026-07-13", wait=14)

    r1 = await send(c, "my plan", wait=5)
    ok1 = "cooking" in r1.lower() and "day" in r1.lower() and ("today" in r1.lower() or "jul" in r1.lower())
    r2 = await send(c, "/plan", wait=5)
    ok2 = "cooking" in r2.lower() and r2.count("\n") >= 3

    print("1 'my plan' shows schedule:", "PASS" if ok1 else f"FAIL → {r1[:200]}")
    print("2 /plan shows schedule:", "PASS" if ok2 else f"FAIL → {r2[:200]}")

    for g in sb.table("goals").select("id").ilike("name", "%cooking%").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute()
        sb.table("goals").delete().eq("id", g["id"]).execute()
    print("[cleaned cooking goal]")
    await c.disconnect()

asyncio.run(main())
