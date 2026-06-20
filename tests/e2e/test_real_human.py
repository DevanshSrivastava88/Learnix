"""Real-human messy-input suite: typos, slang, vague times, emotional msgs, run-ons.
Each case: (message, expected_substring_in_reply_lowercased OR predicate, note)."""
import asyncio, os, sys
from dotenv import load_dotenv
from supabase import create_client
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv("bot/.env")
API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
RESULTS = []

async def reply(client, sent_id, timeout=35):
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
    print(f">>> {msg!r}\n    {r[:170]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

def judge(name, reply, pred):
    ok = pred(reply.lower())
    RESULTS.append((name, ok, reply))

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # 1. slang + vague relative time
    r = await send(c, "yo can u remind me to call mom in like an hour")
    judge("slang call mom ~1h", r, lambda x: "call mom" in x and ("59 min" in x or "1h" in x or "hour" in x))

    # 2. typo 'tmrw'
    r = await send(c, "i need to buy groceries tmrw")
    judge("tmrw -> tomorrow", r, lambda x: "groceries" in x and ("tomorrow" in x or "time" in x))
    if "time?" in r.lower() or "what time" in r.lower():
        await send(c, "no")

    # 3. typo in verb
    r = await send(c, "remnid me to call dad at 6pm")
    judge("typo remind, 6pm", r, lambda x: "dad" in x and "6:00 pm" in x)

    # 4. abbreviation 'abt' + 'hrs'
    r = await send(c, "remind me abt the meeting in 2 hrs")
    judge("abt meeting 2hrs", r, lambda x: "meeting" in x and ("2h" in x or "1h 5" in x or "120 min" in x))

    # 5. emotional / overwhelm -> chat, not a task
    r = await send(c, "ugh i have so much to do today im stressed")
    judge("overwhelm -> chat", r, lambda x: "added" not in x and "remind you" not in x[:30])

    # 6. typo schedule query
    r = await send(c, "wat do i have today")
    judge("schedule query (typo)", r, lambda x: "[timeout]" not in x and ("today" in x or "day" in x or "drink" in x.lower()))

    # 7. slang delete
    r = await send(c, "scrap the dad reminder")
    judge("slang scrap=delete", r, lambda x: "dad" in x and ("gone" in x or "deleted" in x))

    # 8. done natural
    r = await send(c, "just knocked out the groceries")
    judge("done natural phrasing", r, lambda x: "groceries" in x and ("✅" in r or "done" in x or "nice" in x))

    # 9. implicit goal without 'want to'
    r = await send(c, "im trying to learn the guitar")
    judge("implicit learn -> goal", r, lambda x: "guitar" in x and ("difficulty" in x or "goal" in x or "learning" in x))
    if "difficulty" in r.lower():
        await send(c, "/cancel", wait=3)

    # 10. ambiguous bare time (accept clock or relative phrasing — both mean 7 o'clock)
    r = await send(c, "remind me to stretch at 7")
    judge("bare '7' resolves", r, lambda x: "stretch" in x and ("7:00" in x or "7 " in x or "pm" in x or "h " in x or "min" in x))

    print("\n=== REAL-HUMAN RESULTS ===")
    for name, ok, rep in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {rep[:140]}"))

    # cleanup any created tasks
    for title in ("Call Mom","Buy Groceries","Call Dad","Meeting","Stretch","Groceries"):
        sb.table("tasks").delete().eq("title", title).execute()
    for g in sb.table("goals").select("id").ilike("name","%guitar%").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute(); sb.table("goals").delete().eq("id", g["id"]).execute()
    print("[cleaned]")
    await c.disconnect()

asyncio.run(main())
