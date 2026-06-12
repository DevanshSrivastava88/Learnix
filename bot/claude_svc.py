import os
import json
import re
import time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()

MODEL = "llama-3.1-8b-instant"
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
            max_retries=0,
        )
    return _client


def _with_retry(fn, retries: int = 4, base_delay: float = 1.0):
    """Retry on Groq rate limits (429) with exponential backoff."""
    for attempt in range(retries):
        try:
            return fn()
        except RateLimitError:
            if attempt == retries - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


SYSTEM = (
    "You are Learnix, a sharp and friendly study coach. "
    "Explain topics clearly and conversationally — like a knowledgeable friend, not a textbook. "
    "Use concrete examples. Keep it engaging."
)


def _ask(prompt: str, max_tokens: int = 1024) -> str:
    resp = _with_retry(lambda: _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    ))
    return resp.choices[0].message.content.strip()


def _ask_json(prompt: str, max_tokens: int = 512, model: str = None) -> dict | list:
    """Call Groq with JSON mode — forces clean JSON output, no markdown."""
    resp = _with_retry(lambda: _get_client().chat.completions.create(
        model=model or MODEL,
        messages=[
            {"role": "system", "content": "You are a JSON extraction assistant. Always respond with valid JSON only, no markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    ))
    text = resp.choices[0].message.content.strip()
    result = json.loads(text)
    # If wrapped in a list, unwrap
    if isinstance(result, dict):
        # Check if it's actually a list stored under a key
        for v in result.values():
            if isinstance(v, list):
                return v
    return result


def _ask_json_array(prompt: str, max_tokens: int = 1024) -> list:
    """Call Groq expecting a JSON array — wraps in object for JSON mode compatibility."""
    wrapped_prompt = prompt + '\n\nIMPORTANT: Return JSON object with key "items" containing the array: {"items": [...]}'
    resp = _with_retry(lambda: _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a JSON extraction assistant. Always respond with valid JSON only, no markdown, no explanation."},
            {"role": "user", "content": wrapped_prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    ))
    text = resp.choices[0].message.content.strip()
    result = json.loads(text)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                return v
    raise ValueError("Expected JSON array")


def teach_topic(title: str, notes: str = "") -> str:
    if notes.strip():
        prompt = (
            f"{SYSTEM}\n\n"
            f"Teach me about: **{title}**\n\n"
            f"My notes:\n{notes}\n\n"
            "Explain it in 3-4 paragraphs using my notes as the primary source."
        )
    else:
        prompt = (
            f"{SYSTEM}\n\n"
            f"Teach me about: **{title}**\n\n"
            "Explain it clearly in 3-4 paragraphs. Be concise but complete."
        )
    return _ask(prompt)


def generate_quiz(title: str, notes: str = "") -> list[dict]:
    context = f"Notes:\n{notes}\n\n" if notes.strip() else ""
    prompt = (
        f"{context}"
        f"Generate exactly 5 quiz questions about: {title}\n\n"
        "Return a JSON object with key 'items' containing an array:\n"
        '{"items": [{"question": "...", "expected_answer": "..."}, ...]}'
        "\nTest understanding, not just recall. Keep expected_answer to 1-3 sentences."
    )
    result = _ask_json(prompt, max_tokens=2048)
    if isinstance(result, list):
        return result[:5]
    raise ValueError("generate_quiz: expected JSON array")


def score_answer(question: str, expected_answer: str, user_answer: str) -> dict:
    prompt = (
        "You are a strict but fair quiz grader.\n\n"
        f"Question: {question}\n"
        f"Expected answer: {expected_answer}\n"
        f"User's answer: {user_answer}\n\n"
        "Return a JSON object: "
        '{"correct": true/false, "explanation": "1-2 sentences"}\n'
        "Be lenient with phrasing but strict on concept."
    )
    return _ask_json(prompt, max_tokens=150)


def classify_intent(text: str, context: str = "") -> str:
    """Classify free-form message into one of: task | show_tasks | show_schedule |
    show_progress | show_goals | show_graph | show_skipgraph | start_study | study |
    show_topics | study_topic | skip_topic |
    breakdown | done | skip_task | delete_task | pause_task | mark_important | delay |
    set_time | reschedule_task | add_topic | manage_goal | clear_data | show_help |
    show_settings | create_goal | twilio | chat"""
    context_block = f'Recent conversation:\n{context}\n\n' if context else ""
    result = _ask_json(
        f'{context_block}'
        f'Classify this message into exactly one category. Message: "{text}"\n\n'
        f'Categories (name: meaning — example):\n'
        f'task: add/create a reminder, habit, or todo — needs an explicit tracking word: "add X", "track X", "remind me to X", "X every day/daily", "ping me to X", "don\'t let me forget to X"\n'
        f'show_tasks: see tasks/habits list — "show my tasks", "what am I tracking", "give me my task list", "show me what I just added", "what do I have going on", "list", "tasks", "my tasks", "show list"\n'
        f'show_schedule: see today\'s schedule/day plan — "what\'s my day", "my schedule", "give me a rundown of today", "what\'s on my plate", "am I forgetting anything today", "what should I do today"\n'
        f'show_progress: see study progress/stats — "how am I doing with my studies", "my study stats", "how far along am I in learning"\n'
        f'show_goals: see study goals — "my goals", "what am I learning", "what am I studying", "show my learning goals", "what study goals do I have"\n'
        f'show_graph: see activity graph/productivity stats — "my activity", "show my streak", "how productive have I been", "how have I been doing lately", "show my progress chart"\n'
        f'show_skipgraph: see skip patterns — "my skip stats", "what did I skip most", "what do I skip the most", "when do I usually bail"\n'
        f'start_study: start a study session now — "let\'s study", "quiz me", "quiz me on something", "I want to practice", "let\'s review"\n'
        f'study: asking an educational QUESTION to be taught right now — "explain recursion", "what is a closure in JS", "teach me about photosynthesis" '
        f'(NOT "I want to learn X" or "teach me X" as a subject/skill — those are create_goal)\n'
        f'show_topics: see numbered topic list for a goal — "show my topics", "list topics for Python", "list my study topics"\n'
        f'study_topic: study/jump to a SPECIFIC named topic — "study OOP Basics", "jump to File I/O"\n'
        f'skip_topic: skip a SPECIFIC named topic — "skip Error Handling topic"\n'
        f'breakdown: break a task/goal into steps — contains "break down", "steps for", "roadmap for", "plan out", "subtopics for", "break X into steps", "help me plan out X"\n'
        f'done: reporting completion of a task — "I finished X", "done with X", "just knocked out X", "done!", "Done!", "just did it", "finished!"\n'
        f'skip_task: skip a task today — "skip X today", "not doing X today", "gonna skip X for today", "skip it today", "skipping it", "not doing it today"\n'
        f'delete_task: permanently delete a task — "delete X", "remove X habit"\n'
        f'pause_task: pause reminders for a task temporarily — "pause X", "stop reminding me about X"\n'
        f'reschedule_task: change reminder TIME of a SPECIFIC named task — "move my reading reminder to 8pm", "set morning workout to 7am", "push my X reminder to Y" '
        f'(names a task AND a new time for IT)\n'
        f'set_time: change a SYSTEM-WIDE time — morning brief / study session / EOD — "set my morning brief to 8am", "change study time to 9pm", "I usually study at Xpm", "I wake up at Xam" '
        f'(system category, not a specific task name)\n'
        f'add_topic: add a topic to a study goal — "add recursion to my Python goal"\n'
        f'delay: snooze an EXISTING reminder — "delay", "snooze", "delay 30 mins", "remind me later", "snooze X reminder by Y", "snooze the X reminder by Y hours" '
        f'(NOT "remind me that/this in X mins" — that\'s "task")\n'
        f'mark_important: mark a specific task as important — "mark workout as important", "X is urgent", "flag X as priority", "X is really important", "that one is really important mark it", "this is important flag it"\n'
        f'manage_goal: delete/pause/edit a study goal — "delete my Python goal", "pause my React goal"\n'
        f'clear_data: delete all data and start fresh — "reset everything", "wipe my data"\n'
        f'twilio: toggle phone call missed-call notifications — "turn on phone calls", "stop calling me", "notify me when someone calls", "let me know when someone calls me", "call alerts on/off"\n'
        f'show_help: what bot can do / command list — "help", "what can you do for me", "how do you work", "what are your features"\n'
        f'show_settings: see reminder time settings — "show my settings", "what are my current settings", "what time do you remind me"\n'
        f'create_goal: CREATE a new learning goal for a SUBJECT — "I want to learn React", "teach me Python", "I want to get better at X" '
        f'(names a subject to learn, not an existing topic)\n'
        f'chat: greeting, small talk, joke, feelings, general question — also the default when unsure\n\n'
        f'Priority rules when multiple could match:\n'
        f'1. reschedule_task > set_time when a specific task+time vs a system-wide category+time\n'
        f'2. create_goal > start_study/study when user names a subject they want to LEARN OVER TIME ("I want to learn X", "I want to get better at X"). '
        f'Use "study" only for an immediate educational question about a concept.\n'
        f'3. breakdown > study when message says "break down"/"steps for"/"break X into steps"\n'
        f'4. study_topic/skip_topic > others when a specific named topic + study/skip/jump verb\n'
        f'5. done/skip_task/delete_task/pause_task/mark_important > others when a specific task name + that action verb\n'
        f'6. task > delay when user says "remind me that/this in X mins" (context gives the subject)\n'
        f'7. Use "task" for: (a) explicit tracking word: "add", "track", "remind me", "set a reminder", "every day", "daily", "ping me", "don\'t let me forget"; '
        f'OR (b) [activity/event] + [time expression] — implicit reminders: '
        f'"meeting at 6" -> task, "call at 3pm" -> task, "doctor at 9am" -> task, "dinner at 8" -> task, '
        f'"drink water in 10" -> task, "meds in 30" -> task, "sleep in 2 hours" -> task, "gym at 7" -> task. '
        f'NEVER "task" for: conversational statements, planning talk, suggestions, typos — '
        f'"let\'s fix some things" -> chat, "let\'s do this" -> chat, "we should deploy" -> chat, '
        f'"before deploying" -> chat, "shall we tackle something?" -> chat, '
        f'"I should exercise more" -> chat, "im trying to lose weight" -> chat.\n'
        f'8. task > study/create_goal/start_study when the message has a tracking/recurrence phrase '
        f'("every day", "daily", "every morning", "every night") about a general HABIT/activity (read, exercise, meditate, mediation, yoga, journal, walk, run, pushups) — '
        f'"i wanna read evry single day" -> task, "meditate every morning" -> task, "workout every day" -> task. '
        f'Only use create_goal when a SPECIFIC learnable subject is named (Python, React, guitar theory, Spanish grammar, machine learning).\n'
        f'9. delay > task when the message contains "snooze" or "snooze X by Y" pattern referring to an existing named reminder.\n'
        f'10. show_graph > show_goals/show_progress when message asks about productivity, activity level, or "how have I been doing" (graph shows ACTIVITY data, not study progress).\n'
        f'11. set_time > task/chat when the message says "I usually study at/around X", "I study at X", "I normally study at X" — these express a preferred study time, not a task to track.\n'
        f'12. Default to "chat" when genuinely unsure.\n\n'
        f'Return: {{"intent": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return result.get("intent", "chat")
    return "chat"


def understand_message(text: str, context: str = "") -> dict:
    """Single LLM call: classify intent AND extract task fields in one shot.
    Returns {"intent": str, "task": dict|None}.
    task = {"type": "reminder"|"habit", "title": str, "description": str,
            "time_minutes": int|None, "recurrence_days": int, "clarify": str}
    """
    from datetime import datetime
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M %p IST (%A)")
    context_block = f'Recent conversation:\n{context}\n\n' if context else ""
    prompt = (
        f'{context_block}'
        f'Current time: {now_str} (IST = UTC+5:30)\n'
        f'Analyze this message: "{text}"\n\n'
        f'Step 1 — classify intent (exactly one):\n'
        f'task: add a reminder/habit/todo — "add X", "track X", "remind me to X", "X every day", '
        f'or [activity]+[time]: "meeting at 6", "drink water in 10", "meds in 30"\n'
        f'show_tasks: "show my tasks", "list", "what am I tracking"\n'
        f'show_schedule: "what\'s my day", "my schedule", "what should I do today"\n'
        f'show_progress: "how am I doing with studies", "study stats"\n'
        f'show_goals: "my goals", "what am I learning"\n'
        f'show_graph: "my activity", "my streak", "how productive have I been"\n'
        f'show_skipgraph: "what did I skip most"\n'
        f'start_study: "let\'s study", "quiz me"\n'
        f'study: educational question to answer NOW — "explain recursion", "what is a closure"\n'
        f'show_topics: "show my topics", "list topics for Python"\n'
        f'study_topic: study a SPECIFIC named topic — "study OOP Basics"\n'
        f'skip_topic: skip a SPECIFIC named topic\n'
        f'breakdown: "break down X", "steps for X", "roadmap for X"\n'
        f'done: "I finished X", "done", "did it"\n'
        f'skip_task: "skip X today", "not doing X today"\n'
        f'delete_task: "delete X", "remove X", "cancel X", "cancel it/that" (cancel an existing task/reminder)\n'
        f'pause_task: "pause X", "stop reminding me about X"\n'
        f'reschedule_task: change time of an EXISTING named task — "move reading to 8pm", '
        f'"set drink water to 11pm", "set [task] to [time]"\n'
        f'set_time: system-wide times (morning brief/study/EOD) — "set morning brief to 8am", "I usually study at 9pm"\n'
        f'add_topic: "add recursion to my Python goal"\n'
        f'delay: snooze EXISTING reminder — "delay", "snooze 30 mins", "remind me later"\n'
        f'mark_important: "mark X important", "X is urgent", "flag it"\n'
        f'manage_goal: "delete my Python goal", "pause my React goal"\n'
        f'clear_data: "reset everything", "wipe my data"\n'
        f'twilio: "turn on/off phone calls", "call alerts"\n'
        f'show_help: "help", "what can you do"\n'
        f'show_settings: "show my settings"\n'
        f'create_goal: learn a SUBJECT over time — "I want to learn React", "teach me Python"\n'
        f'chat: greeting, small talk, feelings, OR gibberish/typos with no clear meaning ("mo", "asdf") — default when unsure\n\n'
        f'Key rules:\n'
        f'- "cancel it/that" right after a task was added → delete_task (use conversation context)\n'
        f'- Gibberish or 1-2 letter fragments → chat, NEVER task\n'
        f'- done/skip/delete/pause need an EXISTING task reference; adding new → task\n'
        f'- "remind me that/this in X mins" → task (not delay)\n'
        f'- conversational statements ("I should exercise more", "let\'s fix things") → chat\n'
        f'- recurrence phrase + general activity ("read every day") → task; named learnable subject ("learn Python") → create_goal\n\n'
        f'Step 2 — IF AND ONLY IF intent is "task", also extract:\n'
        f'- type: "habit" ONLY with explicit recurrence words (every day, daily, weekly); else "reminder"\n'
        f'- title: 3-5 words, noun phrase, no action verbs (add/track/remind me to), no time in it. '
        f'"add call mom" → "Call Mom", "meeting at 6" → "Meeting"\n'
        f'- description: extra detail or ""\n'
        f'- time_minutes: ONLY for relative durations — "in 30 mins" → 30, "1 hr" → 60. '
        f'Absolute clock time or no time → null. NEVER guess a time.\n'
        f'- time_hhmm: ONLY for absolute clock times, 24h format — "at 8pm" → "20:00", '
        f'"at 11 pm" → "23:00". Do NOT compute minutes for these. Relative or no time → null.\n'
        f'- recurrence_days: 1=daily, 7=weekly (habits only)\n'
        f'- clarify: "" almost always. NEVER ask about time — missing time is fine (task stored unscheduled, '
        f'bot follows up separately). Only fill clarify if the task itself is unintelligible.\n\n'
        f'Step 3 — IF intent is done/skip_task/delete_task/pause_task/mark_important, set task_ref:\n'
        f'the name of the task the user refers to. RESOLVE PRONOUNS from conversation context — '
        f'"cancel it" right after "Added Stretch Break" → task_ref="Stretch Break". '
        f'Bare "done"/"skip" with no referent anywhere → task_ref="".\n\n'
        f'Return ONLY:\n'
        f'{{"intent": "...", "task": {{"type": "...", "title": "...", "description": "", '
        f'"time_minutes": null, "time_hhmm": null, "recurrence_days": 1, "clarify": ""}} or null, "task_ref": ""}}'
    )
    # 70B for routing (8B misclassifies); fall back to 8B if 70B daily quota exhausted
    try:
        result = _ask_json(prompt, max_tokens=250, model="llama-3.3-70b-versatile")
    except Exception:
        result = _ask_json(prompt, max_tokens=250)
    if isinstance(result, dict) and result.get("intent"):
        intent = result.get("intent", "chat")
        task_ref = str(result.get("task_ref") or "").strip()
        task = result.get("task")
        # 8B model often puts the referenced task in task.title instead of task_ref
        if (not task_ref and intent in ("done", "skip_task", "delete_task", "pause_task", "mark_important")
                and isinstance(task, dict) and task.get("title")):
            task_ref = str(task["title"]).strip()
        return {"intent": intent, "task": task, "task_ref": task_ref}
    return {"intent": "chat", "task": None, "task_ref": ""}


def extract_task_name_from_message(text: str) -> str:
    """Extract the task name the user is referring to in a done/skip/delete/pause message."""
    result = _ask_json(
        f'Extract the task name the user is referring to from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "I finished my workout" -> {{"task_name": "workout"}}\n'
        f'  "done with Python studying" -> {{"task_name": "Python studying"}}\n'
        f'  "skip meditation today" -> {{"task_name": "meditation"}}\n'
        f'  "delete my running habit" -> {{"task_name": "running"}}\n'
        f'  "pause reading reminders" -> {{"task_name": "reading"}}\n'
        f'  "my therapy appointment is really important, flag it" -> {{"task_name": "therapy appointment"}}\n'
        f'  "the morning workout is urgent, mark it" -> {{"task_name": "morning workout"}}\n'
        f'  "my daily walk is super important" -> {{"task_name": "daily walk"}}\n'
        f'  "yep did it" -> {{"task_name": ""}}\n'
        f'  "done" -> {{"task_name": ""}}\n'
        f'  "done!" -> {{"task_name": ""}}\n'
        f'  "Done!" -> {{"task_name": ""}}\n'
        f'  "skip" -> {{"task_name": ""}}\n'
        f'  "yeah finished" -> {{"task_name": ""}}\n'
        f'  "mark that as important" -> {{"task_name": ""}}\n'
        f'  "skip it today" -> {{"task_name": ""}}\n'
        f'  "mark it important" -> {{"task_name": ""}}\n'
        f'  "skip that for today" -> {{"task_name": ""}}\n\n'
        f'Key rule: when message names a SPECIFIC NOUN ("therapy appointment", "morning workout", "daily walk") '
        f'followed by "flag it"/"mark it"/"important" — extract that noun as the task name.\n'
        f'If ONLY a pronoun is used ("it", "that", "this") with NO preceding noun in the same message, return "".\n'
        f'If message names NO specific task (bare confirmations like "did it"/"yep"/"done"/"done!"/"finished"/"skip"), return "".\n'
        f'Return: {{"task_name": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        name = str(result.get("task_name", "")).strip()
        return "" if name.lower() in ("none", "null", "n/a") else name
    return ""


def extract_topic_name(text: str) -> str:
    """Extract the topic name from a study/skip/jump message."""
    result = _ask_json(
        f'Extract the study topic name the user is referring to from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "study OOP Basics" -> {{"topic_name": "OOP Basics"}}\n'
        f'  "jump to File I/O" -> {{"topic_name": "File I/O"}}\n'
        f'  "skip Error Handling topic" -> {{"topic_name": "Error Handling"}}\n'
        f'  "do Functions now" -> {{"topic_name": "Functions"}}\n\n'
        f'Return just the topic name as a short clean string.\n'
        f'Return: {{"topic_name": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return result.get("topic_name", "").strip()
    return ""


def extract_breakdown_subject(text: str) -> str:
    """Extract the subject from a breakdown request (e.g. 'break down morning workout' -> 'morning workout')."""
    result = _ask_json(
        f'Extract the thing the user wants to break down from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"subject": "the thing to break down"}}\n'
        f'Example: "break down morning workout" -> {{"subject": "morning workout"}}\n'
        f'Example: "steps for Learn Python" -> {{"subject": "Learn Python"}}\n'
        f'Just return the subject as a clean string, nothing else.',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return result.get("subject", text).strip()
    return text


def breakdown_task(task_name: str) -> list[str]:
    """Returns list of 3-7 concrete step strings for a given task."""
    result = _ask_json_array(
        f'Generate 3 to 7 concrete, actionable steps to complete this task: "{task_name}"\n\n'
        f'Rules:\n'
        f'- Each step should be a short, action-oriented phrase (3-8 words)\n'
        f'- Steps should be ordered logically\n'
        f'- Do NOT number them — just the text\n'
        f'Example for "Morning workout": ["Warmup stretches", "5-minute jog", "Push-ups 3x15", "Cool down"]'
    )
    if not isinstance(result, list):
        raise ValueError("Expected JSON array of steps")
    return [str(s).strip() for s in result if str(s).strip()]


def breakdown_study_goal(goal_name: str, difficulty: str = "medium") -> list[str]:
    """Returns ordered topic list. Difficulty controls depth."""
    _DIFFICULTY_SPECS = {
        "easy":   ("4 to 5",  "broad overview topics, surface-level — skip advanced concepts"),
        "medium": ("6 to 8",  "balanced coverage from foundational to intermediate"),
        "hard":   ("10 to 14", "thorough and comprehensive, include advanced and edge-case topics"),
    }
    count_range, depth_hint = _DIFFICULTY_SPECS.get(difficulty, _DIFFICULTY_SPECS["medium"])
    result = _ask_json_array(
        f'Generate an ordered learning path of {count_range} subtopics for this learning goal: "{goal_name}"\n\n'
        f'Depth: {depth_hint}\n'
        f'Rules:\n'
        f'- Order them from foundational to advanced\n'
        f'- Each subtopic should be a clear, concise phrase (2-6 words)\n'
        f'- Cover the most important aspects of the topic\n'
        f'- Do NOT number them — just the text\n'
        f'Example for "Learn Python": ["Variables & Data Types", "Control Flow", "Functions", "Lists & Dicts", "File I/O", "OOP Basics"]'
    )
    if not isinstance(result, list):
        raise ValueError("Expected JSON array of topics")
    return [str(s).strip() for s in result if str(s).strip()]


def parse_task(text: str, context: str = "") -> dict:
    """Parse natural language task. Returns type: reminder | habit.
    Note: interval_reminder is no longer generated — 'every hour' style is treated as a habit (recurrence_days=1).
    """
    from datetime import datetime
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(IST)
    now_str = now_ist.strftime("%Y-%m-%d %H:%M %p IST (%A)")
    context_block = f"Recent conversation:\n{context}\n\n" if context else ""
    prompt = (
        f"{context_block}Current date and time: {now_str}. Extract task info from this message: \"{text}\"\n\n"
        "Return ONLY a JSON object, no markdown:\n"
        "{\n"
        "  \"type\": \"reminder\" or \"habit\",\n"
        "  \"title\": \"short task name (3-5 words)\",\n"
        "  \"description\": \"optional detail or empty string\",\n"
        "  \"time_str\": \"ONLY if user explicitly stated a time/duration — e.g. '6:20pm', '9am', 'in 30 minutes', 'tomorrow 8am'. If NO time in message → empty string. NEVER infer or suggest a time.\",\n"
        "  \"recurrence_days\": integer (for habits — 1=daily, 7=weekly),\n"
        "  \"clarify\": \"one question if critical info is missing, else empty string\"\n"
        "}\n\n"
        "Rules:\n"
        "- 'reminder': DEFAULT type for any task/todo WITHOUT explicit recurrence.\n"
        "  If time given → set time_str to clean normalized time. If NO time in message → time_str MUST be empty string. Do NOT add tomorrow, tonight, or any guessed time.\n"
        "  Examples: 'meeting at 6' → time_str='6pm', 'call at 6 20' → time_str='6:20pm',\n"
        "  'meeting zat 6 20' → time_str='6:20pm' (interpret typos), 'in 30 mins' → time_str='in 30 minutes'\n"
        "- 'habit': ONLY with explicit recurrence words: 'every day', 'daily', 'every morning',\n"
        "  'every night', 'every week', 'weekly', 'every Monday', 'each day', 'regularly', 'routine'\n"
        "  Examples: 'drink water every day' → habit, 'remind me to drink water' → reminder\n"
        "- Keep title short (3-5 words), noun-phrase, NO leading action verbs, NO time in title\n"
        "  BAD: 'Meeting At 6', 'Add Daily Journaling', '6:20 Meeting'\n"
        "  GOOD: 'Meeting', 'Daily Journaling', 'Call Dad'\n"
        "  Strip: add, track, remind me to, set, schedule, create, start, do, ping me to, don't let me forget to\n"
        "- Only ask clarify if genuinely ambiguous\n"
        "- Never include time in title field"
    )
    result = _ask_json(prompt, max_tokens=200)
    if isinstance(result, dict):
        import re as _re_pt
        title = result.get("title", "")
        # Strip leading action verbs
        title = _re_pt.sub(
            r'^(?:add|track|set|create|schedule|start|do|get|make|build|ping me to|'
            r'remind me to|remind me about|don\'t let me forget to|let me not forget to)\s+',
            '', title, flags=_re_pt.IGNORECASE,
        ).strip()
        # Strip time expressions from title (LLM sometimes embeds them)
        title = _re_pt.sub(
            r'\b(?:at|by|@)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
            '', title, flags=_re_pt.IGNORECASE,
        ).strip()
        title = _re_pt.sub(
            r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b',
            '', title, flags=_re_pt.IGNORECASE,
        ).strip()
        title = _re_pt.sub(r'\s{2,}', ' ', title).strip()
        if title:
            result["title"] = title
        return result
    return {}


def parse_time_only(text: str):
    """Parse a natural language time expression into UTC datetime. Returns datetime or None."""
    from datetime import datetime, timezone, timedelta
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(IST)
    now_str = now_ist.strftime("%Y-%m-%d %H:%M %p IST (%A)")
    result = _ask_json(
        f'Current time: {now_str} (IST = UTC+5:30)\n'
        f'Parse this time expression.\n'
        f'Expression: "{text}"\n\n'
        f'RELATIVE durations → minutes:\n'
        f'  "1 hr" → {{"minutes": 60}}\n'
        f'  "30 mins" / "30m" / "half hour" → {{"minutes": 30}}\n'
        f'  "next hour" → {{"minutes": 60}}\n'
        f'ABSOLUTE clock times → 24h HH:MM (do NOT compute minutes yourself):\n'
        f'  "8pm" → {{"hhmm": "20:00"}}\n'
        f'  "11 pm" → {{"hhmm": "23:00"}}\n'
        f'  "tomorrow 9am" → {{"hhmm": "09:00", "tomorrow": true}}\n\n'
        f'If not a valid time expression, return {{"minutes": 0}}\n'
        f'Return ONLY one JSON object.',
        max_tokens=40,
    )
    if isinstance(result, dict):
        hhmm = result.get("hhmm")
        if hhmm:
            try:
                h, m = map(int, str(hhmm).split(":"))
                target = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
                if result.get("tomorrow") or target <= now_ist:
                    target += timedelta(days=1)
                return target.astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
        mins = result.get("minutes", 0)
        try:
            mins = int(mins)
        except (TypeError, ValueError):
            mins = 0
        if mins > 0:
            return datetime.now(timezone.utc) + timedelta(minutes=mins)
    return None


def extract_set_time_info(text: str) -> dict:
    """Extract which time to set (morning/study/eod) and the time value from a set_time message."""
    result = _ask_json(
        f'Extract time-setting info from this message.\n'
        f'Message: "{text}"\n\n'
        f'time_type options:\n'
        f'- "morning": morning brief, morning reminder, wake-up, brief, "wake me up", '
        f'"morning", "start my day", "good morning"\n'
        f'- "study": study session, study time, study reminder, daily study, '
        f'"I want to study at X", "study at X", "study time", "learning session"\n'
        f'- "eod": EOD, end of day, evening check-in, night reminder, '
        f'"I sleep by X", "I usually sleep at X", "bedtime", "night", "evening wrap-up"\n'
        f'- "": unclear/ambiguous\n\n'
        f'time_value: extract the time as HH:MM in 24h format. '
        f'Convert 12h to 24h (e.g. "8am" → "08:00", "9pm" → "21:00", "10:30pm" → "22:30", '
        f'"11" with sleep/night context → "23:00"). '
        f'Return empty string if no time given.\n\n'
        f'Return: {{"time_type": "...", "time_value": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return {"time_type": result.get("time_type", ""), "time_value": result.get("time_value", "")}
    return {"time_type": "", "time_value": ""}


def extract_reschedule_info(text: str) -> dict:
    """Extract task name and new time from a reschedule_task message."""
    result = _ask_json(
        f'Extract the specific task/habit name and new reminder time from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "remind me about workout at 6am" → {{"task_name": "workout", "time": "06:00"}}\n'
        f'  "move my reading reminder to 8pm" → {{"task_name": "reading", "time": "20:00"}}\n'
        f'  "change pushup time to 5pm" → {{"task_name": "pushup", "time": "17:00"}}\n'
        f'  "set morning workout to 7am" → {{"task_name": "morning workout", "time": "07:00"}}\n'
        f'  "shift my meditation to 9pm" → {{"task_name": "meditation", "time": "21:00"}}\n\n'
        f'task_name: the specific habit/task name (short, clean string)\n'
        f'time: new time as HH:MM in 24h format. Convert 12h → 24h. '
        f'Return empty string if no time given.\n\n'
        f'Return: {{"task_name": "...", "time": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return {"task_name": result.get("task_name", "").strip(), "time": result.get("time", "").strip()}
    return {"task_name": "", "time": ""}


def extract_goal_name_from_message(text: str) -> str:
    """Extract the subject/goal name from a 'create_goal' or 'manage_goal' message."""
    result = _ask_json(
        f'Extract the learning subject or goal name from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "I want to learn React" → {{"goal_name": "React"}}\n'
        f'  "teach me Python" → {{"goal_name": "Python"}}\n'
        f'  "delete my Python goal" → {{"goal_name": "Python"}}\n'
        f'  "pause my React goal" → {{"goal_name": "React"}}\n'
        f'  "edit my Machine Learning goal name" → {{"goal_name": "Machine Learning"}}\n\n'
        f'Return just the subject name as a clean string.\n'
        f'Return: {{"goal_name": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return result.get("goal_name", "").strip()
    return ""


def extract_manage_goal_action(text: str) -> str:
    """Extract what the user wants to do with a goal: delete, pause, or edit."""
    result = _ask_json(
        f'Extract the action the user wants to perform on a study goal.\n'
        f'Message: "{text}"\n\n'
        f'Actions:\n'
        f'- "delete": remove/delete/get rid of the goal\n'
        f'- "pause": pause/stop/freeze the goal temporarily\n'
        f'- "edit": edit/rename/update/change the goal\n'
        f'- "": unclear\n\n'
        f'Return: {{"action": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return result.get("action", "").strip()
    return ""


def extract_add_topic_info(text: str) -> dict:
    """Extract topic name and goal name from an 'add_topic' message."""
    result = _ask_json(
        f'Extract topic and goal from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "add recursion to my Python goal" → {{"topic_name": "Recursion", "goal_name": "Python"}}\n'
        f'  "add topic Binary Trees" → {{"topic_name": "Binary Trees", "goal_name": ""}}\n'
        f'  "I want to add Decorators to my learning" → {{"topic_name": "Decorators", "goal_name": ""}}\n\n'
        f'Return goal_name as empty string if not mentioned.\n'
        f'Return: {{"topic_name": "...", "goal_name": "..."}}',
        max_tokens=100,
    )
    if isinstance(result, dict):
        return {"topic_name": result.get("topic_name", "").strip(), "goal_name": result.get("goal_name", "").strip()}
    return {"topic_name": "", "goal_name": ""}


def transcribe_voice(file_path: str) -> str:
    """Transcribe a voice/audio file using Groq Whisper.

    Accepts .oga/.ogg (Telegram voice notes). Returns the transcribed text.
    """
    with open(file_path, "rb") as f:
        transcription = _get_client().audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            response_format="text",
        )
    return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()


def daily_summary(status: dict) -> str:
    prompt = (
        "Write a punchy daily learning reminder (under 150 words, use emojis, Telegram Markdown).\n\n"
        f"Status: {json.dumps(status)}\n\n"
        "Include: greeting, progress summary, goal status (on track / behind), "
        "today's target topic, one motivating line."
    )
    return _ask(prompt, max_tokens=4096)
