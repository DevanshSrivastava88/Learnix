"""Verify plan advances: complete a topic in DB, /progress + study move to the next."""
import asyncio, os, sys
from dotenv import load_dotenv
from supabase import create_client
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv("bot/.env")
API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
UID = 584321397

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
    print(f">>> {msg!r}\n    {r[:180]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    await send(c, "i want to learn biology", wait=4)
    await send(c, "easy", wait=4)
    await send(c, "2026-07-13", wait=14)

    # find the goal + its first topic, mark it completed directly
    g = sb.table("goals").select("id,name").ilike("name", "%biology%").execute().data[0]
    topics = sb.table("topics").select("id,title,order_index").eq("goal_id", g["id"]).order("order_index").execute().data
    first = topics[0]
    sb.table("topics").update({"status": "completed", "score": "5/5"}).eq("id", first["id"]).execute()
    print(f"[marked completed: {first['title']}]\n")

    # progress should now show 1/N done and a DIFFERENT up-next topic
    r1 = await send(c, "how am i doing with biology", wait=5)
    ok1 = ("1/" in r1) and (first["title"].lower() not in r1.lower().split("up next")[-1])

    # study should now offer the SECOND topic, not the completed first
    r2 = await send(c, "study biology", wait=12)
    ok2 = first["title"].lower() not in r2.lower() and "day" in r2.lower()

    print("1 progress advanced (1 done, next differs):", "PASS" if ok1 else f"FAIL → {r1[:200]}")
    print("2 study picks next topic:", "PASS" if ok2 else f"FAIL → {r2[:200]}")

    await send(c, "/cancel", wait=3)
    # cleanup
    sb.table("topics").delete().eq("goal_id", g["id"]).execute()
    sb.table("goals").delete().eq("id", g["id"]).execute()
    print("[cleaned biology goal]")
    await c.disconnect()

asyncio.run(main())
