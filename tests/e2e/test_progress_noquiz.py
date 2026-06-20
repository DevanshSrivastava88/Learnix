"""Isolated: 'how far am i on X' returns PROGRESS, never starts a quiz. Generous waits."""
import asyncio, os, sys
from dotenv import load_dotenv
from supabase import create_client
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv("bot/.env")
API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

async def newest(client, after_id, settle=10):
    """Wait `settle`s after the last new message, return final newest text."""
    end = asyncio.get_event_loop().time() + settle
    txt = "[none]"
    while asyncio.get_event_loop().time() < end:
        ms = sorted([m for m in await client.get_messages(BOT, limit=8) if m.id > after_id and not m.out], key=lambda x: x.id)
        if ms:
            txt = ms[-1].text or "[media]"
        await asyncio.sleep(1)
    return txt

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    async def sid():
        m = await c.get_messages(BOT, limit=1); return m[0].id if m else 0

    # clear stuck quiz/flow
    await c.send_message(BOT, "/cancel"); await asyncio.sleep(4)

    # create a planned goal, wait long for the plan build
    await c.send_message(BOT, "i want to learn typing"); await asyncio.sleep(5)
    await c.send_message(BOT, "easy"); await asyncio.sleep(4)
    s = await sid(); await c.send_message(BOT, "next month")
    plan = await newest(c, s, settle=18)
    print("PLAN:", plan[:160], "\n")

    # THE TEST: progress query must NOT start a quiz
    s = await sid(); await c.send_message(BOT, "how far am i on typing")
    r = await newest(c, s, settle=10)
    print("PROGRESS QUERY REPLY:", r[:200], "\n")
    is_quiz = "q1/" in r.lower() or "quiz" in r.lower() or "teaching" in r.lower() or r.lower().startswith("**q")
    is_progress = "day" in r.lower() or "progress" in r.lower() or "topics done" in r.lower() or "track" in r.lower()
    print("RESULT:", "PASS" if (is_progress and not is_quiz) else "FAIL")

    # cleanup
    for g in sb.table("goals").select("id").ilike("name","%typing%").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute(); sb.table("goals").delete().eq("id", g["id"]).execute()
    await c.send_message(BOT, "/cancel")
    print("[cleaned]")
    await c.disconnect()

asyncio.run(main())
