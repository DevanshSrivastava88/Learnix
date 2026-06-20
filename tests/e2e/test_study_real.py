"""Real-human study-flow suite: relative deadlines, casual study/progress phrasing."""
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

_TRANSIENT = ("building your study plan", "teaching")
async def reply(client, sent_id, timeout=45):
    """Return the newest non-transient bot reply after sent_id. Waits for the build
    placeholder to be replaced by the real message so replies don't misalign."""
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        msgs = sorted([m for m in await client.get_messages(BOT, limit=8)
                       if m.id > sent_id and not m.out], key=lambda x: x.id)
        if msgs:
            newest = (msgs[-1].text or "[no text]")
            if not any(k in newest.lower() for k in _TRANSIENT):
                return newest  # settled on a real reply
        await asyncio.sleep(1)
    return msgs[-1].text if msgs else "[timeout]"

async def send(c, msg, wait=9):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r[:170]!r}\n")
    await asyncio.sleep(wait)
    return r or ""

def judge(name, reply, pred):
    RESULTS.append((name, pred(reply.lower()), reply))

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()
    await send(c, "/cancel", wait=2)  # clear any stuck quiz/flow from a prior run

    # 1. casual goal intent
    r = await send(c, "i wanna get good at python", wait=4)
    judge("casual goal intent", r, lambda x: "python" in x and ("difficulty" in x or "goal" in x))
    await send(c, "medium", wait=4)
    # 2. relative deadline (real users don't type ISO dates)
    r = await send(c, "next month", wait=15)
    judge("relative deadline 'next month'", r, lambda x: "study plan" in x or "plan" in x or "topics" in x)

    # 3. casual plan view
    r = await send(c, "whats my plan look like", wait=5)
    judge("casual plan view", r, lambda x: "python" in x and ("day" in x or "today" in x))

    # 4. casual progress
    r = await send(c, "how far am i on python", wait=5)
    judge("casual progress", r, lambda x: "python" in x and ("day" in x or "%" in x or "topic" in x))

    # 5. behind check
    r = await send(c, "am i behind on python", wait=5)
    judge("behind check", r, lambda x: "python" in x or "track" in x or "day" in x)

    # 6. pause goal casual
    r = await send(c, "pause python im too busy", wait=5)
    judge("casual pause goal", r, lambda x: "paused" in x and "python" in x)

    # 7. resume casual
    r = await send(c, "ok resume python", wait=5)
    judge("casual resume goal", r, lambda x: "active" in x or "back on" in x)

    print("\n=== STUDY REAL-HUMAN RESULTS ===")
    for name, ok, rep in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {rep[:150]}"))

    for g in sb.table("goals").select("id").ilike("name","%python%").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute(); sb.table("goals").delete().eq("id", g["id"]).execute()
    print("[cleaned python goal]")
    await c.disconnect()

asyncio.run(main())
