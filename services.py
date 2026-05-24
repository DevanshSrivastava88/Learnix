import os
import json
import base64
from datetime import datetime
import requests
import anthropic
import pytz

IST = pytz.timezone("Asia/Kolkata")
GITHUB_API = "https://api.github.com"
GITHUB_REPO = os.getenv("GITHUB_REPO", "DevanshSrivastava88/Learnix")
GITHUB_BRANCH = "master"


class GitHubService:
    def __init__(self):
        self.headers = {
            "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _get_file(self, path: str):
        r = requests.get(
            f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}",
            headers=self.headers,
            params={"ref": GITHUB_BRANCH},
        )
        r.raise_for_status()
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]

    def get_status(self) -> dict:
        content, _ = self._get_file("status.json")
        data = json.loads(content)
        if "goals" not in data:
            data["goals"] = []
        return data

    def update_status(self, new_data: dict):
        _, sha = self._get_file("status.json")
        new_data["last_updated"] = datetime.now(IST).strftime("%Y-%m-%d")
        encoded = base64.b64encode(json.dumps(new_data, indent=2).encode()).decode()
        requests.put(
            f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/status.json",
            headers=self.headers,
            json={
                "message": f"chore: update progress {new_data['last_updated']}",
                "content": encoded,
                "sha": sha,
                "branch": GITHUB_BRANCH,
            },
        )

    def get_module_content(self, folder: str, filename: str) -> str:
        content, _ = self._get_file(f"{folder}/{filename}")
        return content

    def update_module_status(self, folder: str, module_id: int, status: str, score: str):
        data = self.get_status()
        today = datetime.now(IST).strftime("%Y-%m-%d")
        for topic in data["topics"]:
            if topic["folder"] == folder:
                for module in topic["modules"]:
                    if module["id"] == module_id:
                        module["status"] = status
                        module["score"] = score
                        module["date"] = today
        self.update_status(data)

    def update_module_result(self, folder: str, filename: str, score: int, status: str):
        try:
            content, sha = self._get_file(f"{folder}/{filename}")
            today = datetime.now(IST).strftime("%Y-%m-%d")
            label = "PASSED" if score >= 3 else "NEEDS REVISION"
            result = f"\n## Result\nDate: {today}\nScore: {score}/5\nStatus: {label}\n"
            if "## Result" in content:
                content = content.split("## Result")[0] + result
            else:
                content += result
            encoded = base64.b64encode(content.encode()).decode()
            requests.put(
                f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{folder}/{filename}",
                headers=self.headers,
                json={
                    "message": f"chore: update {filename} result",
                    "content": encoded,
                    "sha": sha,
                    "branch": GITHUB_BRANCH,
                },
            )
        except Exception:
            pass


class ClaudeService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-6"

    def teach_module(self, module_name: str, content: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Teach me "{module_name}" as a sharp, engaging teacher.\n\n'
                        f"Notes:\n{content}\n\n"
                        "Explain key concepts in 3-4 short paragraphs. Use real examples. "
                        "Be conversational, not textbook-y. "
                        'End with exactly: "Ready for your quiz? Here comes Q1:"'
                    ),
                }
            ],
        )
        return resp.content[0].text

    def generate_quiz(self, module_name: str, content: str) -> list:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Generate 5 quiz questions for "{module_name}".\n\nNotes:\n{content}\n\n'
                        "Return ONLY a JSON array, no other text:\n"
                        '[{"question": "...", "answer": "..."}, ...]'
                        "\nMix MCQ and short answer. Test real understanding."
                    ),
                }
            ],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    def score_answer(self, question: str, correct: str, user_answer: str) -> tuple:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\nCorrect answer: {correct}\nStudent: {user_answer}\n\n"
                        "First line: CORRECT or WRONG\n"
                        "Second line: 1-sentence explanation (include correct answer if wrong)"
                    ),
                }
            ],
        )
        lines = resp.content[0].text.strip().split("\n", 1)
        is_correct = lines[0].strip().upper().startswith("CORRECT")
        explanation = lines[1].strip() if len(lines) > 1 else correct
        return is_correct, explanation

    def daily_summary(self, status: dict) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=350,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Write a punchy daily learning reminder (under 150 words, use emojis, Telegram Markdown).\n\n"
                        f"Status: {json.dumps(status)}\n\n"
                        "Include: greeting, progress summary, goal status (on track / behind by X), "
                        "today's target module, one motivating line."
                    ),
                }
            ],
        )
        return resp.content[0].text
