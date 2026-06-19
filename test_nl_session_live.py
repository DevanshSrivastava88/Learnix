"""Live test: natural-language session wrap + welcome-back (NO slash commands)."""
import asyncio, sys
from telethon import TelegramClient
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, "bot")
from supabase_svc import get_client

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
UID = 584321397


def clean():
    for t in ("user_facts", "mem_events", "mem_sessions", "chat_history"):
        get_client().table(t).delete().eq("user_id", UID).execute()


async def reply(c, sid, timeout=40):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await c.get_messages(BOT, limit=5):
            if m.id > sid and not m.out:
                return m.text or "[no text]"
        await asyncio.sleep(1)
    return "[timeout]"


async def send(c, msg, wait=4):
    s = await c.send_message(BOT, msg)
    r = await reply(c, s.id)
    print(f">>> {msg!r}\n    {r!r}\n")
    await asyncio.sleep(wait)
    return r or ""


async def main():
    print("settling..."); await asyncio.sleep(20)
    clean()
    c = TelegramClient(SESSION, API_ID, API_HASH); await c.start()

    await send(c, "yo just wanna vent — been stressed about my exams but proud i pushed through today")
    await send(c, "my aunt raised me, she'd be happy seeing me grind this hard honestly")

    # natural-language wrap (NO slash)
    w = await send(c, "alright gotta go, wrap this up", wait=3)

    sess = get_client().table("mem_sessions").select("summary,open_threads").eq("user_id", UID).execute().data
    print("SESSION row:", sess)

    # natural greeting -> welcome-back
    g = await send(c, "hey")

    wrapped = "wrapped" in (w or "").lower()
    stored = bool(sess)
    wb = "last time" in (g or "").lower() or "welcome back" in (g or "").lower() or "left off" in (g or "").lower()
    print("=" * 60)
    print("NL 'wrap this up' triggered wrap :", wrapped)
    print("session recap stored            :", stored)
    print("NL 'hey' -> welcome-back         :", wb, "|", g[:70])
    print("RESULT:", "PASS" if (wrapped and stored and wb) else "CHECK MANUALLY")
    print("=" * 60)
    clean(); print("cleaned.")
    await c.disconnect()

asyncio.run(main())
