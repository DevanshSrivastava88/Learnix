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
    """Classify free-form message as: task | study | chat"""
    result = _ask_json(
        f'Classify this message into exactly one category.\n'
        f'Message: "{text}"\n\n'
        f'Categories:\n'
        f'- "task": user wants to create a reminder, habit, todo, or track something\n'
        f'- "study": user wants to learn something, asks a question, or mentions studying\n'
        f'- "chat": general conversation, greeting, or anything else\n\n'
        f'Return: {{"intent": "task" | "study" | "chat"}}'
    )
    return result.get("intent", "chat")


def parse_task(text: str) -> dict:
    """Parse natural language task description into structured data."""
    from datetime import date
    today = date.today().isoformat()
    prompt = (
        f"Today is {today}. Extract task info from this message: \"{text}\"\n\n"
        "Return ONLY a JSON object, no markdown:\n"
        "{\n"
        "  \"type\": \"habit\" or \"milestone\",\n"
        "  \"title\": \"short task name\",\n"
        "  \"description\": \"optional detail or empty string\",\n"
        "  \"recurrence_days\": 1 (for habits — 1=daily, 7=weekly, etc.),\n"
        "  \"target_date\": \"YYYY-MM-DD\" or null (for milestones),\n"
        "  \"clarify\": \"one question to ask if critical info is missing, else empty string\"\n"
        "}\n\n"
        "Rules:\n"
        "- If it sounds like a recurring action (workout, read, meditate, remind), it's a habit\n"
        "- If it sounds like a one-time project/goal with a deadline, it's a milestone\n"
        "- Only ask for clarification if type is genuinely ambiguous\n"
        "- Keep title short (3-5 words max)"
    )
    return _ask_json(prompt)


def daily_summary(status: dict) -> str:
    prompt = (
        "Write a punchy daily learning reminder (under 150 words, use emojis, Telegram Markdown).\n\n"
        f"Status: {json.dumps(status)}\n\n"
        "Include: greeting, progress summary, goal status (on track / behind), "
        "today's target topic, one motivating line."
    )
    return _ask(prompt, max_tokens=300)
