"""NVIDIA NIM proof-of-concept LLM provider.

Drop-in alternative to claude_svc.py using the OpenAI-compatible NIM API
(integrate.api.nvidia.com/v1).  Same function signatures — to switch, replace:

    import claude_svc as llm
with:
    import nim_svc as llm

Required env var: NIM_API_KEY  (get from build.nvidia.com)

Note: transcribe_voice is not implemented — NIM has no audio endpoint.
      For voice, keep claude_svc.transcribe_voice or use OpenAI Whisper.
"""
import os
import json
from datetime import datetime
from openai import OpenAI
import pytz

MODEL = "meta/llama-3.1-70b-instruct"
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.environ["NIM_API_KEY"],
        )
    return _client


def _ask(prompt: str, max_tokens: int = 1024) -> str:
    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def _ask_json(prompt: str) -> dict | list:
    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=8192,
    )
    return json.loads(resp.choices[0].message.content.strip())


SYSTEM = (
    "You are Learnix, a sharp and friendly study coach. "
    "Explain topics clearly and conversationally — like a knowledgeable friend, not a textbook. "
    "Use concrete examples. Keep it engaging."
)


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


def classify_intent(text: str, context: str = "") -> str:
    context_block = f'Recent conversation:\n{context}\n\n' if context else ""
    result = _ask_json(
        f'{context_block}'
        f'Classify this message into exactly one category.\n'
        f'Message: "{text}"\n\n'
        f'Categories: task | show_tasks | show_schedule | show_progress | show_goals | '
        f'show_graph | show_skipgraph | start_study | study | show_topics | study_topic | '
        f'skip_topic | breakdown | done | skip_task | delete_task | pause_task | '
        f'mark_important | delay | set_time | reschedule_task | add_topic | manage_goal | '
        f'clear_data | show_help | show_settings | create_goal | twilio | chat\n\n'
        f'- "task": ADD/CREATE a reminder, habit, or todo\n'
        f'- "show_tasks": SEE their tasks/habits list\n'
        f'- "show_schedule": see today\'s schedule\n'
        f'- "show_progress": see study progress/stats\n'
        f'- "show_goals": see study goals\n'
        f'- "show_graph": activity graph\n'
        f'- "show_skipgraph": skip patterns graph\n'
        f'- "start_study": start a study session\n'
        f'- "study": educational question or learn a topic\n'
        f'- "show_topics": see numbered topic list for a goal\n'
        f'- "study_topic": study a specific named topic\n'
        f'- "skip_topic": skip a specific named topic\n'
        f'- "breakdown": break task/goal into steps (break down, steps for, roadmap)\n'
        f'- "done": report completing a specific task\n'
        f'- "skip_task": skip a specific task today\n'
        f'- "delete_task": permanently delete/remove a task\n'
        f'- "pause_task": pause reminders for a specific task\n'
        f'- "mark_important": mark a task as high-priority\n'
        f'- "delay": snooze an existing reminder\n'
        f'- "set_time": change morning brief/study session/EOD time (system-wide)\n'
        f'- "reschedule_task": change reminder time of a specific named task\n'
        f'- "add_topic": add a topic to a study goal\n'
        f'- "manage_goal": delete/pause/edit a goal\n'
        f'- "clear_data": delete all user data\n'
        f'- "show_help": see command list\n'
        f'- "show_settings": see reminder time settings\n'
        f'- "create_goal": CREATE a new learning goal for a subject\n'
        f'- "twilio": toggle phone call reminders on/off\n'
        f'- "chat": greeting, small talk, general question\n\n'
        f'Return: {{"intent": "..."}}'
    )
    return result.get("intent", "chat")


def extract_task_name_from_message(text: str) -> str:
    result = _ask_json(
        f'Extract the task name the user is referring to from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"task_name": "..."}}'
    )
    return result.get("task_name", "").strip()


def extract_topic_name(text: str) -> str:
    result = _ask_json(
        f'Extract the study topic name the user is referring to from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"topic_name": "..."}}'
    )
    return result.get("topic_name", "").strip()


def extract_breakdown_subject(text: str) -> str:
    result = _ask_json(
        f'Extract the thing the user wants to break down from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"subject": "the thing to break down"}}'
    )
    return result.get("subject", text).strip()


def breakdown_task(task_name: str) -> list[str]:
    result = _ask_json(
        f'Generate 3 to 7 concrete, actionable steps to complete this task: "{task_name}"\n\n'
        f'Rules: each step is a short action phrase (3-8 words), ordered logically.\n'
        f'Return a JSON array of strings: ["step 1", "step 2", ...]'
    )
    if isinstance(result, list):
        return [str(s).strip() for s in result if str(s).strip()]
    raise ValueError("breakdown_task: expected JSON array")


def breakdown_study_goal(goal_name: str, difficulty: str = "medium") -> list[str]:
    _DIFFICULTY_SPECS = {
        "easy":   ("4 to 5",  "broad overview topics, surface-level — skip advanced concepts"),
        "medium": ("6 to 8",  "balanced coverage from foundational to intermediate"),
        "hard":   ("10 to 14", "thorough and comprehensive, include advanced and edge-case topics"),
    }
    count_range, depth_hint = _DIFFICULTY_SPECS.get(difficulty, _DIFFICULTY_SPECS["medium"])
    result = _ask_json(
        f'Generate an ordered learning path of {count_range} subtopics for: "{goal_name}"\n\n'
        f'Depth: {depth_hint}\n'
        f'Order from foundational to advanced. Each subtopic is a clear phrase (2-6 words).\n'
        f'Return a JSON array of strings: ["topic 1", "topic 2", ...]'
    )
    if isinstance(result, list):
        return [str(s).strip() for s in result if str(s).strip()]
    raise ValueError("breakdown_study_goal: expected JSON array")


def parse_task(text: str, context: str = "") -> dict:
    IST = pytz.timezone("Asia/Kolkata")
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M %p IST (%A)")
    context_block = f"Recent conversation:\n{context}\n\n" if context else ""
    prompt = (
        f"{context_block}Current date and time: {now_str}. "
        f'Extract task info from this message: "{text}"\n\n'
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "type": "reminder" or "habit",\n'
        '  "title": "short task name (3-5 words)",\n'
        '  "description": "optional detail or empty string",\n'
        '  "delay_minutes": integer (for reminders — minutes from now),\n'
        '  "recurrence_days": integer (for habits — 1=daily, 7=weekly),\n'
        '  "clarify": "one question if critical info missing, else empty string"\n'
        "}\n\n"
        "Rules:\n"
        "- 'reminder': one-time (in X mins, at 5pm)\n"
        "- 'habit': recurring (every day, daily, every morning)\n"
        "- For reminder: delay_minutes as integer, recurrence_days null\n"
        "- For habit: recurrence_days (default 1), delay_minutes null"
    )
    return _ask_json(prompt)


def extract_set_time_info(text: str) -> dict:
    result = _ask_json(
        f'Extract time-setting info from this message.\n'
        f'Message: "{text}"\n\n'
        f'time_type: "morning" | "study" | "eod" | ""\n'
        f'time_value: HH:MM in 24h format, or "" if not given.\n\n'
        f'Return: {{"time_type": "...", "time_value": "..."}}'
    )
    return {"time_type": result.get("time_type", ""), "time_value": result.get("time_value", "")}


def extract_reschedule_info(text: str) -> dict:
    result = _ask_json(
        f'Extract the specific task/habit name and new reminder time from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"task_name": "...", "time": "HH:MM in 24h"}}'
    )
    return {"task_name": result.get("task_name", "").strip(), "time": result.get("time", "").strip()}


def extract_goal_name_from_message(text: str) -> str:
    result = _ask_json(
        f'Extract the learning subject or goal name from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"goal_name": "..."}}'
    )
    return result.get("goal_name", "").strip()


def extract_manage_goal_action(text: str) -> str:
    result = _ask_json(
        f'Extract the action the user wants to perform on a study goal.\n'
        f'Message: "{text}"\n\n'
        f'Actions: "delete" | "pause" | "edit" | ""\n\n'
        f'Return: {{"action": "..."}}'
    )
    return result.get("action", "").strip()


def extract_add_topic_info(text: str) -> dict:
    result = _ask_json(
        f'Extract topic and goal from this message.\n'
        f'Message: "{text}"\n\n'
        f'Return: {{"topic_name": "...", "goal_name": "..."}}'
    )
    return {"topic_name": result.get("topic_name", "").strip(), "goal_name": result.get("goal_name", "").strip()}


def daily_summary(status: dict) -> str:
    prompt = (
        "Write a punchy daily learning reminder (under 150 words, use emojis, Telegram Markdown).\n\n"
        f"Status: {json.dumps(status)}\n\n"
        "Include: greeting, progress summary, goal status (on track / behind), "
        "today's target topic, one motivating line."
    )
    return _ask(prompt, max_tokens=4096)


def transcribe_voice(file_path: str) -> str:
    raise NotImplementedError(
        "NIM has no audio endpoint. Use claude_svc.transcribe_voice (Gemini Files API) "
        "or switch to OpenAI Whisper: openai.audio.transcriptions.create(model='whisper-1', file=...)"
    )
