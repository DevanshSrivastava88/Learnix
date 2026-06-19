"""
Casual phrasing + context-memory test suite for @Quest3131Bot.
Tests every major feature WITHOUT using /commands — pure natural language.
Also tests multi-turn context chains where bot must remember prior messages.

Run: python test_casual.py
"""

import asyncio
import csv
import sys
from telethon import TelegramClient

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID   = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"
BOT      = "@Quest3131Bot"
SESSION  = "learnix_tester"
WAIT     = 28

# ─────────────────────────────────────────────────────────────────────────────
# Format: (label, message, [keywords])
# label starts with '#' → setup step (no record)
# label starts with '##' → longer wait setup (5s)
# ─────────────────────────────────────────────────────────────────────────────
TESTS = [

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 1 — Core: help / info via casual phrasing
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CC1_help_casual",     "what can you do for me",              ["task","remind","study","habit","command","help"]),
    ("CC2_help_casual2",    "how do you work",                     ["task","remind","study","habit","command","help"]),
    ("CC3_info_casual",     "explain yourself",                    ["task","remind","study","habit","track","info"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 2 — Tasks: every action in casual form
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    # create habit
    ("CC4_new_habit",       "i want to meditate every morning",    ["look right","daily","meditat","got it"]),
    ("#cancel",             "/cancel",                             []),
    ("CC5_new_habit2",      "add daily journaling to my routine",  ["look right","daily","journal","got it"]),
    ("#cancel",             "/cancel",                             []),
    # create reminder with time
    ("CC6_reminder",        "ping me to take my meds at 9pm",      ["got it","med","9","remind"]),
    # create reminder without time
    ("CC7_reminder_notime", "don't let me forget to call dad",     ["got it","call","dad","look right"]),
    ("#cancel",             "/cancel",                             []),
    # show tasks
    ("CC8_show_tasks",      "what am i tracking",                  ["tracking","task","habit","no task"]),
    ("CC9_show_tasks2",     "give me my task list",                ["tracking","task","habit","no task"]),
    # mark done
    ("CC10_done",           "just knocked out my pushups",         ["done","streak","pushup","don't see","couldn't"]),
    # skip
    ("CC11_skip",           "gonna skip journaling for today",     ["skip","remind","journal","don't see"]),
    # delay
    ("CC12_delay",          "snooze the meds reminder by an hour", ["delay","hour","remind","med","got it","no recent"]),
    # important flag
    ("CC13_important",      "my therapy appointment is really important, flag it",
                                                                   ["important","therapy","flag","don't see"]),
    # reschedule
    ("CC14_reschedule",     "push my call dad reminder to 8pm",    ["remind","call","dad","8","done","don't see"]),
    # break into steps
    ("CC15_breakdown",      "help me break losing 10kg into steps",["step","broke","weight","lose","kg","adding"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 3 — Schedule
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),
    ("CC16_schedule",       "give me a rundown of today",          ["day","morning","schedule","habit","automatic"]),
    ("CC17_schedule2",      "what's on my plate right now",        ["day","morning","schedule","habit","automatic"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 4 — Analytics
    # ══════════════════════════════════════════════════════════════════════════
    ("CC18_graph",          "how productive have i been lately",   ["graph","activity","generating","day","chart"]),
    ("CC19_skipgraph",      "what do i skip the most",             ["skip","graph","pattern","generating","chart"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 5 — Settings
    # ══════════════════════════════════════════════════════════════════════════
    ("CC20_settings",       "what are my current settings",        ["morning","study","eod","setting","time"]),
    ("CC21_setmorning",     "i wake up at 7am, set my brief then", ["done","morning","7","set","brief"]),
    ("CC22_setstudytime",   "i usually study around 10pm",         ["done","study","10","set","time"]),
    ("CC23_calls_on",       "let me know when someone calls me",   ["call","on","number","share","phone"]),
    ("CC24_calls_off",      "stop the call notifications",         ["off","call","pause","disabled","stop"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 6 — Study: every action in casual form
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CC25_create_goal",    "i want to get better at python",      ["goal","python","learn","difficulty","easy","medium","hard"]),
    ("#cancel",             "/cancel",                             []),
    ("CC26_show_goals",     "what am i studying right now",        ["goal","no goal","study","learn"]),
    ("CC27_show_topics",    "list my study topics",                ["topic","no topic","goal"]),
    ("CC28_start_study",    "quiz me on something",                ["study","topic","teach","goal","quiz","no "]),
    ("#cancel",             "/cancel",                             []),
    ("CC29_progress",       "how far along am i in learning",      ["progress","study","streak","goal","no ","percent","%"]),
    ("CC30_study_session",  "i want to practice some coding today",["study","quiz","topic","goal","let","practice","no "]),
    ("#cancel",             "/cancel",                             []),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 7 — Context memory: weight loss chain
    # Bot must carry context from one message to the next
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CTX1_topic_set",      "i've been struggling with my diet lately",
                                                                   ["diet","weight","track","habit","goal","health","help","struggle"]),
    ("CTX2_remind_this",    "remind me to track my calories every day",
                                                                   ["got it","calori","daily","track","look right"]),
    ("#cancel",             "/cancel",                             []),
    ("CTX3_show_that",      "show me what i just added",           ["calori","track","task","tracking","added"]),
    ("CTX4_skip_it",        "skip that for today",                 ["skip","calori","remind","track","don't see"]),
    ("CTX5_mark_important", "actually that one is really important, mark it",
                                                                   ["important","calori","track","mark","don't see"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 8 — Context memory: pronoun chain after adding task
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CTX6_add_task",       "remind me to do a 20 min walk every morning",
                                                                   ["look right","daily","walk","got it","20"]),
    ("#cancel",             "/cancel",                             []),
    ("CTX7_mark_it",        "mark that as important",              ["important","walk","mark","flag","don't see"]),
    ("CTX8_change_time",    "actually change it to evening instead",["remind","walk","evening","done","update","don't see"]),
    ("CTX9_skip_it2",       "skip it today",                       ["skip","walk","remind","today","don't see"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 9 — Context memory: study goal pronoun chain
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CTX10_goal_start",    "i want to learn machine learning",    ["goal","learn","ml","machine","difficulty","easy","medium","hard"]),
    ("#cancel",             "/cancel",                             []),
    ("CTX11_study_ref",     "how am i doing with that",            ["goal","study","progress","learn","machine","no "]),
    ("CTX12_break_it",      "break that goal into steps for me",   ["step","broke","ml","machine","learn","topic","adding"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 10 — Context memory: sleep advice → reminder chain
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    ("CTX13_sleep_topic",   "i've been sleeping really badly lately",
                                                                   ["sleep","rest","routine","tip","bad","sorry","help"]),
    ("CTX14_sleep_advice",  "what should i do to fix it",          ["sleep","routine","bed","tip","try","rest","caffeine","wind"]),
    ("CTX15_remind_that",   "ok remind me to do that every night at 10pm",
                                                                   ["got it","remind","10","night","sleep","wind","routine"]),
    ("CTX16_refer_back",    "and also remind me about it every morning",
                                                                   ["got it","remind","morning","sleep","routine","it"]),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOCK 11 — Mixed complex flows
    # ══════════════════════════════════════════════════════════════════════════
    ("#reset", "/reset", []),

    # bot should detect task + confirm, then follow-up refers to same task
    ("MX1_task_then_time",  "i need to submit my project report",  ["got it","report","submit","look right","project"]),
    ("#cancel",             "/cancel",                             []),
    ("MX2_vague_done",      "done!",                               ["which","done","task","streak","report","mean"]),
    ("MX3_multi_intent",    "remind me to meditate at 7am and also track my water intake daily",
                                                                   ["got it","meditat","water","remind","track","daily"]),
    ("#cancel",             "/cancel",                             []),
    ("MX4_casual_schedule", "am i forgetting anything today",      ["day","morning","schedule","habit","task","automatic","nothing"]),
    ("MX5_introspect",      "what do you know about me",           ["task","habit","goal","study","setting","track","morning"]),
]


async def get_bot_reply(client, sent_id, timeout=WAIT):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        msgs = await client.get_messages(BOT, limit=5)
        for m in msgs:
            if m.id > sent_id and not m.out:
                return m.text or "[media/no text]"
        await asyncio.sleep(1)
    return None


async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()

    total = len([t for t in TESTS if not t[0].startswith('#')])
    results = []
    print(f"\nCasual + Context test — {total} cases\n{'='*55}")

    for label, msg, keywords in TESTS:
        is_setup = label.startswith("#")
        print(f"\n{'[setup]' if is_setup else '[test] ' + label}  ->  {msg!r}")

        sent = await client.send_message(BOT, msg)
        reply = await get_bot_reply(client, sent.id, timeout=WAIT if not is_setup else 6)

        if is_setup:
            await asyncio.sleep(1.5)
            continue

        if reply is None:
            status = "FAIL"
            print(f"  FAIL — no reply within {WAIT}s")
        else:
            hit = any(k.lower() in reply.lower() for k in keywords)
            status = "PASS" if hit else "WARN"
            print(f"  {status}: {reply[:120].replace(chr(10), ' ')}")

        results.append({
            "label":    label,
            "sent":     msg,
            "status":   status,
            "reply":    (reply or "")[:300],
        })
        await asyncio.sleep(9)

    await client.disconnect()

    log = r"D:\Projects\learnix\test_casual_full.log"
    with open(log, "w", encoding="utf-8") as f:
        f.write(f"\nCasual + Context test — {total} cases\n{'='*55}\n\n")
        for r in results:
            f.write(f"[{r['status']}] {r['label']}\n  sent:  {r['sent']}\n  reply: {r['reply']}\n\n")

    out = r"D:\Projects\learnix\test_casual_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["label","sent","status","reply"])
        w.writeheader(); w.writerows(results)

    p  = sum(1 for r in results if r["status"] == "PASS")
    wn = sum(1 for r in results if r["status"] == "WARN")
    fa = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n{'='*55}\nPASS:{p}  WARN:{wn}  FAIL:{fa}")
    print(f"Log:  {log}\nCSV:  {out}")

asyncio.run(main())
