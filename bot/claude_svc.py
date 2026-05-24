"""
claude_svc.py — Claude API interactions: teach, quiz, score.
"""

import os
import json
import re
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client: Optional[anthropic.Anthropic] = None
MODEL = "claude-sonnet-4-6"


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ---------------------------------------------------------------------------
# Teaching
# ---------------------------------------------------------------------------

def teach_topic(title: str, notes: str = "") -> str:
    """
    Ask Claude to explain the topic conversationally in 3-4 paragraphs.
    If notes are provided, use them as additional context/source material.
    """
    client = get_client()

    system = (
        "You are Learnix, a sharp and friendly study coach. "
        "Explain topics clearly and conversationally — like a knowledgeable friend, not a textbook. "
        "Use concrete examples. Keep it engaging. 3–4 paragraphs max."
    )

    if notes.strip():
        user_msg = (
            f"Teach me about: **{title}**\n\n"
            f"Here are my notes/context for this topic:\n{notes}\n\n"
            "Explain it clearly, use my notes as the primary source, "
            "and fill in gaps from your knowledge."
        )
    else:
        user_msg = (
            f"Teach me about: **{title}**\n\n"
            "Explain it clearly from your knowledge. Be concise but complete."
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------

def generate_quiz(title: str, notes: str = "") -> list[dict]:
    """
    Generate 5 quiz questions for the topic.
    Returns list of dicts: [{question: str, expected_answer: str}, ...]
    """
    client = get_client()

    system = (
        "You are Learnix quiz engine. Generate quiz questions as a JSON array. "
        "Each element: {\"question\": \"...\", \"expected_answer\": \"...\"}. "
        "Questions should test understanding, not just recall. "
        "Keep expected_answer concise (1-3 sentences). "
        "Output ONLY valid JSON — no markdown, no extra text."
    )

    context = f"Notes:\n{notes}\n\n" if notes.strip() else ""
    user_msg = (
        f"{context}"
        f"Generate exactly 5 quiz questions about: {title}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    questions = json.loads(raw)
    # Ensure exactly 5
    return questions[:5]


# ---------------------------------------------------------------------------
# Answer scoring
# ---------------------------------------------------------------------------

def score_answer(question: str, expected_answer: str, user_answer: str) -> dict:
    """
    Score a user's answer. Returns:
    {correct: bool, explanation: str}
    """
    client = get_client()

    system = (
        "You are a strict but fair quiz grader. "
        "Evaluate if the user's answer demonstrates understanding of the key concept. "
        "Respond with a JSON object: {\"correct\": true/false, \"explanation\": \"...\"}. "
        "explanation should be 1-2 sentences: confirm what was right, correct what was wrong. "
        "Output ONLY valid JSON."
    )

    user_msg = (
        f"Question: {question}\n"
        f"Expected answer: {expected_answer}\n"
        f"User's answer: {user_answer}\n\n"
        "Is the user's answer correct? Be lenient with phrasing but strict on concept."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)
