import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"
_model = genai.GenerativeModel(MODEL)

SYSTEM = (
    "You are Learnix, a sharp and friendly study coach. "
    "Explain topics clearly and conversationally — like a knowledgeable friend, not a textbook. "
    "Use concrete examples. Keep it engaging."
)


def _ask(prompt: str, max_tokens: int = 1024) -> str:
    resp = _model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )
    return resp.text.strip()


def _ask_json(prompt: str) -> dict | list:
    """Call Gemini with JSON mode — forces clean JSON output, no markdown."""
    resp = _model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            max_output_tokens=8192,
        ),
    )
    return json.loads(resp.text.strip())


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
        "Return a JSON array:\n"
        '[{"question": "...", "expected_answer": "..."}, ...]'
        "\nTest understanding, not just recall. Keep expected_answer to 1-3 sentences."
    )
    result = _ask_json(prompt)
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
    return _ask_json(prompt)


def classify_intent(text: str) -> str:
    """Classify free-form message into one of: task | show_tasks | show_schedule |
    show_progress | show_goals | show_graph | show_skipgraph | start_study | study |
    breakdown | done | skip_task | delete_task | pause_task | chat"""
    result = _ask_json(
        f'Classify this message into exactly one category.\n'
        f'Message: "{text}"\n\n'
        f'Categories:\n'
        f'- "task": user wants to ADD/CREATE a reminder, habit, or todo '
        f'(e.g. "add X", "track X", "I need to X every day", "set a reminder for X", "I want to start X")\n'
        f'- "show_tasks": user wants to SEE their tasks/habits list '
        f'(e.g. "show my tasks", "what do I have to do", "my habits", "what am I tracking", '
        f'"list everything", "show habits", "what\'s on my list", "all my tasks")\n'
        f'- "show_schedule": user wants to see today\'s schedule or day plan '
        f'(e.g. "what\'s my day", "my schedule", "today\'s plan", "plan my day", '
        f'"what\'s today look like", "my day", "day view", "what\'s up for today")\n'
        f'- "show_progress": user wants to see study progress or stats '
        f'(e.g. "how am I doing", "my progress", "study stats", "am I on track", '
        f'"am I improving", "how far am I", "my study stats", "how\'s my Python going", "how\'s learning going")\n'
        f'- "show_goals": user wants to see their study goals '
        f'(e.g. "my goals", "what am I studying", "learning goals", "what am I learning", "show goals")\n'
        f'- "show_graph": user wants to see activity graph or stats '
        f'(e.g. "my activity", "show stats", "how active am I", "how active have I been", '
        f'"show my streak", "how lazy have I been", "activity", "my stats")\n'
        f'- "show_skipgraph": user wants to see skip patterns '
        f'(e.g. "how many times did I skip", "my skip stats", "what did I skip most", '
        f'"skip patterns", "how many times did I skip")\n'
        f'- "start_study": user wants to start a study session now '
        f'(e.g. "let\'s study", "start studying", "teach me", "let\'s do some Python", '
        f'"teach me something", "quiz me", "I want to study", "continue studying")\n'
        f'- "study": user asks an educational question or wants to learn a specific topic\n'
        f'- "breakdown": user wants to break a task OR learning goal into steps/subtopics. '
        f'ALWAYS use this when message contains "break down", "break ... into steps", "steps for", '
        f'"learning path", "subtopics for", "how do I approach", "plan for", "give me a roadmap for", '
        f'"plan out", "structure ... for me". '
        f'Examples: "break down morning workout", "steps for Python", "break my goal into topics", '
        f'"plan out my morning routine", "give me a roadmap for ML"\n'
        f'- "done": user is reporting they completed a specific task '
        f'(e.g. "I finished X", "done with X", "completed X", "just did X", "marked X done")\n'
        f'- "skip_task": user wants to skip a specific task today '
        f'(e.g. "skip X today", "skipping X", "not doing X today")\n'
        f'- "delete_task": user wants to permanently delete/remove a task '
        f'(e.g. "delete X", "remove X habit", "get rid of X")\n'
        f'- "pause_task": user wants to pause/stop reminders for a specific task temporarily '
        f'(e.g. "pause X", "stop reminding me about X for now")\n'
        f'- "chat": clearly just greeting, small talk, joke, feelings, general question\n\n'
        f'IMPORTANT RULES:\n'
        f'- "breakdown" takes priority over "study" when the message contains "break down" or "steps for".\n'
        f'- "done"/"skip_task"/"delete_task"/"pause_task" take priority when user mentions a specific task name with those action words.\n'
        f'- Default to "chat" when genuinely unsure (not "task"). Only use "task" when user clearly wants to CREATE something.\n'
        f'Return: {{"intent": "..."}}'
    )
    return result.get("intent", "chat")


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
        f'  "pause reading reminders" -> {{"task_name": "reading"}}\n\n'
        f'Return just the task name as a short clean string.\n'
        f'Return: {{"task_name": "..."}}'
    )
    return result.get("task_name", "").strip()


def extract_breakdown_subject(text: str) -> str:
    """Extract the subject from a breakdown request (e.g. 'break down morning workout' -> 'morning workout')."""
    result = _ask_json(
        f'Extract the thing the user wants to break down from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"subject": "the thing to break down"}}\n'
        f'Example: "break down morning workout" -> {{"subject": "morning workout"}}\n'
        f'Example: "steps for Learn Python" -> {{"subject": "Learn Python"}}\n'
        f'Just return the subject as a clean string, nothing else.'
    )
    return result.get("subject", text).strip()


def breakdown_task(task_name: str) -> list[str]:
    """Returns list of 3-7 concrete step strings for a given task."""
    result = _ask_json(
        f'Generate 3 to 7 concrete, actionable steps to complete this task: "{task_name}"\n\n'
        f'Rules:\n'
        f'- Each step should be a short, action-oriented phrase (3-8 words)\n'
        f'- Steps should be ordered logically\n'
        f'- Do NOT number them — just the text\n'
        f'- Return a JSON array of strings: ["step 1", "step 2", ...]\n'
        f'Example for "Morning workout": ["Warmup stretches", "5-minute jog", "Push-ups 3x15", "Cool down"]'
    )
    if isinstance(result, list):
        return [str(s).strip() for s in result if str(s).strip()]
    raise ValueError("breakdown_task: expected JSON array")


def breakdown_study_goal(goal_name: str) -> list[str]:
    """Returns list of 5-8 ordered topic strings for a given learning goal."""
    result = _ask_json(
        f'Generate an ordered learning path of 5 to 8 subtopics for this learning goal: "{goal_name}"\n\n'
        f'Rules:\n'
        f'- Order them from foundational to advanced\n'
        f'- Each subtopic should be a clear, concise phrase (2-6 words)\n'
        f'- Cover the most important aspects of the topic\n'
        f'- Do NOT number them — just the text\n'
        f'- Return a JSON array of strings: ["topic 1", "topic 2", ...]\n'
        f'Example for "Learn Python": ["Variables & Data Types", "Control Flow", "Functions", "Lists & Dicts", "File I/O", "OOP Basics"]'
    )
    if isinstance(result, list):
        return [str(s).strip() for s in result if str(s).strip()]
    raise ValueError("breakdown_study_goal: expected JSON array")


def parse_task(text: str) -> dict:
    """Parse natural language task. Returns type: reminder | interval_reminder | habit."""
    from datetime import datetime
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(IST)
    now_str = now_ist.strftime("%Y-%m-%d %H:%M %p IST (%A)")
    prompt = (
        f"Current date and time: {now_str}. Extract task info from this message: \"{text}\"\n\n"
        "Return ONLY a JSON object, no markdown:\n"
        "{\n"
        "  \"type\": \"reminder\" or \"interval_reminder\" or \"habit\",\n"
        "  \"title\": \"short task name (3-5 words)\",\n"
        "  \"description\": \"optional detail or empty string\",\n"
        "  \"delay_minutes\": integer (for reminders — how many minutes from now, e.g. 20),\n"
        "  \"interval_minutes\": integer (for interval_reminder — repeat every X minutes, e.g. 60 for every hour),\n"
        "  \"recurrence_days\": integer (for habits — 1=daily, 7=weekly),\n"
        "  \"clarify\": \"one question if critical info is missing, else empty string\"\n"
        "}\n\n"
        "Rules:\n"
        "- 'reminder': one-time — phrases like 'in 20 mins', 'in 2 hours', 'at 5pm', 'in 10', 'remind me in X'\n"
        "- 'interval_reminder': repeating intra-day — 'every hour', 'every 30 mins', 'every 2 hours', 'remind me every X'\n"
        "- 'habit': daily/weekly — 'every day', 'daily', 'every morning', or no time/delay specified\n"
        "- A bare number like 'in 10' or 'remind in 10' always means 10 minutes (reminder)\n"
        "- For reminder: set delay_minutes as integer minutes from now, others null\n"
        "- For interval_reminder: set interval_minutes (e.g. 60 for hourly, 30 for every 30 min), others null\n"
        "- For habit: set recurrence_days (default 1), others null\n"
        "- Convert hours to minutes: '2 hours' = 120, '1.5 hours' = 90\n"
        "- Only ask clarify if genuinely ambiguous\n"
        "- Keep title short (3-5 words)\n"
        "- If user says 'remind me to X' with NO time information, set type='reminder', delay_minutes=0, "
        "and clarify='When? (e.g. \"in 30 mins\", \"at 8pm\")' — do NOT ask any other question\n"
        "- Never ask 'How many minutes from now?' — always use the above phrasing"
    )
    return _ask_json(prompt)


def daily_summary(status: dict) -> str:
    prompt = (
        "Write a punchy daily learning reminder (under 150 words, use emojis, Telegram Markdown).\n\n"
        f"Status: {json.dumps(status)}\n\n"
        "Include: greeting, progress summary, goal status (on track / behind), "
        "today's target topic, one motivating line."
    )
    return _ask(prompt, max_tokens=4096)
