"""Live: pause a goal by text, then resume it by text (full symmetry)."""
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
    print(f">>> {msg!r}\n    {r[:150]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    await send(c, "i want to learn painting", wait=4)
    await send(c, "easy", wait=4)
    await send(c, "-", wait=14)

    r1 = await send(c, "pause my painting goal")
    ok1 = "paused" in r1.lower()
    # verify DB shows paused
    paused = sb.table("goals").select("status").ilike("name","%painting%").execute().data
    ok_db_paused = paused and paused[0]["status"] == "paused"
    r2 = await send(c, "resume my painting goal")
    ok2 = ("active again" in r2.lower() or "back on" in r2.lower())
    active = sb.table("goals").select("status").ilike("name","%painting%").execute().data
    ok_db_active = active and active[0]["status"] == "in_progress"

    print("1 pause:", "PASS" if ok1 and ok_db_paused else f"FAIL → {r1[:120]} db={paused}")
    print("2 resume:", "PASS" if ok2 and ok_db_active else f"FAIL → {r2[:120]} db={active}")

    for g in sb.table("goals").select("id").ilike("name","%painting%").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute()
        sb.table("goals").delete().eq("id", g["id"]).execute()
    print("[cleaned painting goal]")
    await c.disconnect()

asyncio.run(main())
