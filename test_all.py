"""Comprehensive all-features suite with a ROBUST harness:
- unique session copy per run (dodges sqlite locks)
- settle-based reply capture (waits past 'Building...'/'Teaching...' transients)
- pre-clean of test goals/tasks + /cancel to clear stuck flows
Run: python test_all.py
"""
import asyncio, os, sys, shutil, time
from dotenv import load_dotenv
from supabase import create_client
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
load_dotenv("bot/.env")
API_ID, API_HASH, BOT = 38978049, "d0b46bd9b101c3f25b6be6251d6a2dd2", "@Quest3131Bot"
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
UID = 584321397
KEEP_TASKS = {"Brusj", "Gym"}  # the user's real data — never delete
RESULTS = []
TRANSIENT = ("building your study plan", "teaching", "generating your")

# unique session copy
SESS_SRC = "learnix_tester.session"
SESS = f"_t_{int(time.time())}"
shutil.copyfile(SESS_SRC, SESS + ".session")

async def settled(client, after_id, settle=4.0, timeout=45):
    """Wait until the newest non-transient message after after_id is stable for `settle`s."""
    end = time.time() + timeout
    last_txt, last_change = "[none]", time.time()
    while time.time() < end:
        ms = sorted([m for m in await client.get_messages(BOT, limit=8) if m.id > after_id and not m.out],
                    key=lambda x: x.id)
        cur = ""
        for m in ms:
            t = (m.text or "[media]")
            if not any(k in t.lower() for k in TRANSIENT):
                cur = t
        if cur and cur != last_txt:
            last_txt, last_change = cur, time.time()
        if cur and (time.time() - last_change) >= settle:
            return cur
        await asyncio.sleep(0.8)
    return last_txt

async def step(client, msg, name=None, pred=None, settle=4.0):
    m = await client.get_messages(BOT, limit=1)
    after = m[0].id if m else 0
    await client.send_message(BOT, msg)
    r = await settled(client, after, settle=settle)
    print(f">>> {msg!r}\n    {r[:160]!r}\n")
    if name and pred:
        RESULTS.append((name, pred(r.lower()), r))
    return r

def clean_db():
    for g in sb.table("goals").select("id").execute().data:
        sb.table("topics").delete().eq("goal_id", g["id"]).execute()
        sb.table("goals").delete().eq("id", g["id"]).execute()
    for t in sb.table("tasks").select("id,title,status").in_("status", ["active", "paused", "skipped"]).execute().data:
        if t["title"] not in KEEP_TASKS:
            sb.table("tasks").delete().eq("id", t["id"]).execute()

async def main():
    clean_db()
    c = TelegramClient(SESS, API_ID, API_HASH)
    await c.start()
    await step(c, "/cancel", settle=2)

    # ---------- TASKS ----------
    await step(c, "remind me to call the bank at 3pm", "task: timed 3pm",
               lambda x: "call the bank" in x and "3:00 pm" in x)
    await step(c, "remind me to water plants tomorrow at 8am", "task: tomorrow 8am",
               lambda x: "water plants" in x and "8:00 am" in x and "tomorrow" in x)
    await step(c, "add read a book", "task: untimed asks time",
               lambda x: "read a book" in x and "time" in x)
    await step(c, "no", "task: untimed no->unscheduled", lambda x: "unscheduled" in x or "📌" in x)
    await step(c, "remind me to stretch in 30 mins and meditate in 45 mins", "task: multi-task",
               lambda x: "stretch" in x or "meditate" in x)  # first reply; both created

    # ---------- ACTIONS ----------
    await step(c, "done call the bank", "action: done one-time",
               lambda x: "call the bank" in x and ("✅" in x or "done" in x))
    await step(c, "snooze the meditate reminder by 1 hour", "action: snooze",
               lambda x: "meditate" in x or "snooz" in x or "later" in x or "moved" in x)
    await step(c, "mark stretch as important", "action: mark important",
               lambda x: "stretch" in x and ("important" in x or "⚡" in x))
    await step(c, "move water plants to 9am", "action: reschedule",
               lambda x: "water plants" in x and "9" in x)
    await step(c, "delete read a book", "action: delete",
               lambda x: "read a book" in x and ("gone" in x or "deleted" in x))

    # ---------- HABITS ----------
    await step(c, "add habit drink water every day at 9am", "habit: timed daily",
               lambda x: "drink water" in x and "9:00 am" in x)
    await step(c, "skip drink water today", "habit: skip",
               lambda x: "drink water" in x and "skip" in x)
    await step(c, "pause drink water", "habit: pause",
               lambda x: "drink water" in x and "pause" in x)
    await step(c, "resume drink water", "habit: resume",
               lambda x: "drink water" in x and ("active" in x or "back on" in x))

    # ---------- SUBTASKS ----------
    await step(c, "break down plan a birthday party", "subtask: breakdown proposes",
               lambda x: "yes" in x and ("1." in x or "step" in x), settle=5)
    await step(c, "yes", "subtask: confirm creates",
               lambda x: "added" in x and "subtask" in x)

    # ---------- VIEWS ----------
    await step(c, "list", "view: list", lambda x: "your tasks" in x)
    await step(c, "what do i have today", "view: schedule",
               lambda x: "your day" in x or "automatics" in x or "habits" in x)
    await step(c, "/graph", "view: graph", lambda x: "[media]" in x or "activity" in x or "yet" in x)
    await step(c, "/settings", "view: settings", lambda x: "settings" in x or "study time" in x)
    await step(c, "what can you do", "view: help", lambda x: "study" in x or "task" in x)

    # ---------- STUDY ----------
    await step(c, "i want to learn calligraphy", "study: goal intent",
               lambda x: "calligraphy" in x and ("difficulty" in x or "goal" in x))
    await step(c, "easy", settle=2)
    await step(c, "next month", "study: dated plan built",
               lambda x: "study plan" in x and ("today" in x or "jul" in x), settle=18)
    await step(c, "my plan", "study: /plan view",
               lambda x: "calligraphy" in x and "day" in x)
    await step(c, "how far am i on calligraphy", "study: progress (no quiz)",
               lambda x: ("day" in x or "progress" in x or "track" in x) and "q1/" not in x)
    await step(c, "pause calligraphy im busy", "study: pause goal by text",
               lambda x: "paused" in x and "calligraphy" in x)
    await step(c, "resume calligraphy", "study: resume goal by text",
               lambda x: "active" in x or "back on" in x)
    await step(c, "delete my calligraphy goal", "study: delete goal asks confirm",
               lambda x: "calligraphy" in x and ("yes" in x or "confirm" in x))
    await step(c, "yes", "study: goal deleted", lambda x: "deleted" in x or "gone" in x)

    # ---------- CHAT / PERSONA ----------
    await step(c, "ugh im so tired today", "chat: empathy not task",
               lambda x: "added" not in x and "remind you" not in x[:30])
    await step(c, "/persona flirty", "persona: switch", lambda x: "flirty" in x or "😏" in x)
    await step(c, "/persona normal", "persona: reset", lambda x: "friendly" in x or "🙂" in x)

    # ---------- RESULTS ----------
    print("\n" + "=" * 50)
    p = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, rep in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  → {rep[:120]}"))
    print(f"\n{p}/{len(RESULTS)} passed")

    clean_db()
    await c.send_message(BOT, "/cancel")
    await c.disconnect()

asyncio.run(main())
try:
    os.remove(SESS + ".session")
except OSError:
    pass
