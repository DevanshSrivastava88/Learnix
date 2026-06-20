# legacy/ — superseded v1

These files are the **first version of Learnix** and are no longer used or deployed.
They are kept for reference only. Nothing in the live codebase imports them.

| File | What it was |
|---|---|
| `bot.py` | v1 Telegram bot — single-user, Anthropic SDK, **GitHub repo as the database** (committed Markdown notes/quizzes). |
| `services.py` | v1 service layer: `ClaudeService` (Anthropic) + `GitHubService` (read/write files via the GitHub API). |
| `render.yaml` | Render.com deploy config referencing `GEMINI_API_KEY`. Stale — the live bot deploys on **Railway** (`bot/railway.json`). |
| `env.example.v1` | v1 env template (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO`). |
| `requirements.txt` | v1 root deps (orphaned — incomplete for both v1 and the current bot). |

**The live system lives in `bot/` (Telegram bot) and `web/` (task list).** It uses
Groq + Supabase, not Anthropic + GitHub. See `../ARCHITECTURE.md`.
