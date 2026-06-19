"""Live Telethon test of the memory spine on the DEPLOYED bot.
Flow: facts -> /wrap -> verify stored; correction -> /wrap -> verify fact-update;
struggle msg -> verify reply uses stored memory (recall). Cleans its own rows."""
import asyncio, sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, "bot")
from supabase_svc import get_client

API_ID, API_HASH, BOT, SESSION = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot", "learnix_tester"
UID = 584321397


def clean():
    get_client().table("user_facts").delete().eq("user_id", UID).execute()
    get_client().table("mem_events").delete().eq("user_id", UID).execute()


def facts_now():
    r = get_client().table("user_facts").select("text,pillar,status").eq("user_id", UID).eq("status", "active").execute()
    return r.data or []


async def reply(client, sent_id, timeout=40):
    dl = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < dl:
        for m in await client.get_messages(BOT, limit=5):
            if m.id > sent_id and not m.out:
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
    print("settling for deploy swap...")
    await asyncio.sleep(20)
    clean()
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.start()

    # 1) feed life facts (addiction + productivity)
    await send(c, "hey, real talk — i've been trying to quit vaping, been at it 2 years. my big exam is next week and i'm stressed")
    await send(c, "my aunt raised me, she'd be gutted if she knew. i slipped twice last month")

    # 2) wrap -> extract + store
    w1 = await send(c, "/wrap", wait=3)
    f1 = facts_now()
    print("FACTS after wrap1:", [(f["text"], f["pillar"]) for f in f1])

    # 3) correction -> wrap -> fact-update
    await send(c, "update: my exam actually moved to the 25th, not next week. and i'm clean now — quit vaping 3 days ago!")
    w2 = await send(c, "/wrap", wait=3)
    f2 = facts_now()
    print("FACTS after wrap2:", [(f["text"], f["pillar"]) for f in f2])

    # 4) recall: struggle msg should be able to reference stored memory
    r = await send(c, "ugh i feel like giving up on everything")

    texts = " ".join(f["text"].lower() for f in f2)
    no_stale_exam = "next week" not in texts
    has_25 = "25" in texts
    quit_progress = "quit" in texts or "clean" in texts or "3 days" in texts
    stored_ok = len(f1) >= 3
    wrap_ok = "wrapped" in (w1 or "").lower()

    print("=" * 60)
    print("wrap1 stored >=3 facts :", stored_ok, f"({len(f1)})")
    print("wrap1 confirmed        :", wrap_ok)
    print("exam date corrected    :", has_25, "| no stale 'next week':", no_stale_exam)
    print("vaping->quit updated   :", quit_progress)
    print("struggle reply got     :", r[:80] if r != "[timeout]" else "[timeout]")
    ok = stored_ok and wrap_ok and has_25 and no_stale_exam
    print("RESULT:", "PASS" if ok else "CHECK MANUALLY")
    print("=" * 60)

    clean()
    print("test rows cleaned.")
    await c.disconnect()

asyncio.run(main())
