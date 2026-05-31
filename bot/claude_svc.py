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
    breakdown | chat"""
    result = _ask_json(
        f'Classify this message into exactly one category.\n'
        f'Message: "{text}"\n\n'
        f'Categories:\n'
        f'- "task": user wants to ADD/CREATE a reminder, habit, or todo\n'
        f'- "show_tasks": user wants to SEE their tasks/habits list (e.g. "show my tasks", "what do I have to do", "my habits")\n'
        f'- "show_schedule": user wants to see today\'s schedule or day plan (e.g. "what\'s my day", "my schedule", "today\'s plan")\n'
        f'- "show_progress": user wants to see study progress or stats (e.g. "how am I doing", "my progress", "study stats")\n'
        f'- "show_goals": user wants to see their study goals (e.g. "my goals", "what am I studying", "learning goals")\n'
        f'- "show_graph": user wants to see activity graph or stats (e.g. "my activity", "show stats", "how active am I")\n'
        f'- "show_skipgraph": user wants to see skip patterns (e.g. "how many times did I skip", "my skip stats")\n'
        f'- "start_study": user wants to start a study session now (e.g. "let\'s study", "start studying", "teach me")\n'
        f'- "study": user asks an educational question or wants to learn a specific topic\n'
        f'- "breakdown": user wants to break a task or learning goal into steps/subtopics '
        f'(e.g. "break down X", "steps for X", "break X into steps", "learning path for X", "subtopics for X")\n'
        f'- "chat": clearly just greeting, small talk, joke, feelings, general question\n\n'
        f'Default to "chat" when genuinely unsure (not "task"). Only use "task" when user clearly wants to CREATE something.\n'
        f'Return: {{"intent": "..."}}'
    )
    return result.get("intent", "chat")


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
        "- Keep title short (3-5 words)"
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
