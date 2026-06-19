"""
Automated feature + context tester for disrupto (@Quest3131Bot).
Uses Telethon (user client) — no browser, low token usage.
Run: python test_features.py
"""

import asyncio
import csv
import sys
from telethon import TelegramClient

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API_ID   = 38978049
API_HASH = "d0b46bd9b101c3f25b6be6251d6a2dd2"
BOT      = "@Quest3131Bot"
SESSION  = "learnix_tester"
WAIT     = 25  # seconds to wait for bot reply

# (label, message, [keywords_to_pass])
# prefix with # to use as setup step (send but don't record)
FEATURES = [
    ("#reset",           "/reset",                              []),
    # Basic response
    ("F1_hi",            "hi",                                  ["hi","hey","hello","what","how","help"]),
    ("F2_casual",        "hey whats up",                        ["hey","hi","how","help"]),
    # Task management
    ("F3_reminder",      "remind me to drink water in 2 mins",  ["got it","water","2 min"]),
    ("F4_habit",         "workout every day",                   ["look right","daily","workout"]),
    ("F5_cancel",        "cancel",                              ["cancel","no worries"]),
    ("F6_tasks",         "show my tasks",                       ["tracking","task","habit","no task"]),
    ("#cancel",          "/cancel",                             []),
    ("F7_schedule",      "what's my day",                       ["day","morning","schedule","habit","automatic"]),
    ("#cancel",          "/cancel",                             []),
    ("F8_done",          "I finished morning workout",          ["done","streak","remind","workout"]),
    ("F9_skip",          "skip daily meditation",               ["skip","remind","meditation"]),
    ("F10_reschedule",   "move morning workout to 7am",         ["done","morning","workout","7","remind"]),
    ("F11_delay",        "delay 30 mins",                       ["delay","30","remind","got it"]),
    ("F12_important",    "mark morning workout as important",   ["important","workout","hour","remind"]),
    # Analytics
    ("F13_graph",        "show my activity graph",              ["graph","activity","generating","30 day"]),
    ("F14_skipgraph",    "show my skip patterns",               ["skip","graph","pattern","generating"]),
    # Settings
    ("F15_settings",     "show my settings",                    ["morning","study","eod","setting"]),
    ("F16_set_time",     "set my morning brief to 8am",         ["done","morning","8","set"]),
    # Phone calls
    ("F17_calls_on",     "turn on phone calls reminder",        ["call","on","number","share"]),
    ("F18_calls_off",    "turn off phone calls",                ["off","call","pause"]),
    # Help + reset
    ("F19_help",         "help",                                ["task","reminder","command","can","habit"]),
    # Context awareness
    ("#reset",           "/reset",                              []),
    ("C1_hi_after_reset","hi",                                  ["hi","hey","hello","what","how"]),
    ("C2_topic",         "im trying to lose weight",            ["weight","health","track","goal","tip","chat"]),
    ("C3_remind_this",   "remind me about this every morning",  ["got it","remind","weight","morning","lose"]),
    ("C4_sleep",         "what should I do to sleep better?",   ["sleep","routine","bed","tip","try","rest"]),
    ("C5_remind_that",   "remind me to do that at 10pm",        ["got it","remind","10","sleep","wind","routine"]),
    ("C6_echo_not_task", "shall we tackle something?",          ["sure","yes","let","what","love","happy"]),
    # Casual phrasing — bot should still understand the intent, not just keyword-match
    ("#reset",           "/reset",                              []),
    ("S1_slang_task",    "yo remind me to hit the gym at 6",    ["got it","gym","6","remind"]),
    ("S2_typo_habit",    "i wanna read evry single day",        ["look right","read","daily","every day"]),
    ("S3_vague_done",    "yep did it",                          ["done","streak","worry","which","mean"]),
    ("S4_no_match_task", "mark my guitar practice as done",     ["don't see","couldn't find","which","mean","track"]),
    ("S5_casual_chat",   "ngl today was rough lol",             ["rough","day","ugh","sorry","lol","bad"]),
    ("S6_slangy_skip",   "nah skip the reading thing today",    ["skip","reading","remind"]),
    # Study feature (re-enabled)
    ("#reset",           "/reset",                              []),
    ("ST1_create_goal",  "i want to learn react",               ["goal","learn","react","name","topic","start"]),
    ("#cancel",          "/cancel",                             []),
    ("ST2_show_goals",   "show my study goals",                 ["goal","no goal","learn","study"]),
    ("ST3_show_topics",  "what topics do i have",               ["topic","no topic","goal"]),
    ("ST4_start_study",  "let's study",                         ["study","topic","teach","goal","no "]),
    ("#cancel",          "/cancel",                             []),
    ("ST5_progress",     "how's my study progress",             ["progress","study","streak","goal","no "]),
    # Task features — breakdown, optional time, presentable list
    ("#reset",           "/reset",                              []),
    ("T1_no_time_task",  "remind me to call mom",               ["got it","mom","added","daily","time"]),
    ("T2_optional_time", "skip",                                ["default","got it","time"]),
    ("T3_breakdown",     "break learning guitar into steps",    ["steps","step","guitar","added","broke"]),
    ("T4_tasks_list",    "show my tasks",                       ["tracking","task","timed","no fixed time","mom"]),
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

    results = []
    print(f"\nTesting {len([f for f in FEATURES if not f[0].startswith('#')])} features\n{'='*55}")

    for label, msg, keywords in FEATURES:
        is_setup = label.startswith("#")
        print(f"\n{'[setup]' if is_setup else '[test] '+label}  ->  {msg!r}")

        sent = await client.send_message(BOT, msg)
        reply = await get_bot_reply(client, sent.id, timeout=WAIT if not is_setup else 5)

        if is_setup:
            await asyncio.sleep(1)
            continue

        if reply is None:
            status = "FAIL"
            print(f"  FAIL — no reply within {WAIT}s")
        else:
            hit = any(k.lower() in reply.lower() for k in keywords)
            status = "PASS" if hit else "WARN"
            print(f"  {status}: {reply[:100].replace(chr(10),' ')}")

        results.append({"feature": label, "sent": msg, "status": status, "reply": reply[:200] if reply else ""})
        await asyncio.sleep(8)

    await client.disconnect()

    out = r"D:\Projects\learnix\feature_test_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["feature","sent","status","reply"])
        w.writeheader(); w.writerows(results)

    p = sum(1 for r in results if r["status"]=="PASS")
    w2 = sum(1 for r in results if r["status"]=="WARN")
    fa = sum(1 for r in results if r["status"]=="FAIL")
    print(f"\n{'='*55}\nPASS:{p}  WARN:{w2}  FAIL:{fa}\nResults: {out}")

asyncio.run(main())
