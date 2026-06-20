# tests/e2e — live end-to-end tests

Telethon scripts that drive the **deployed** bot (@Quest3131Bot) as a real Telegram
user and assert on its replies (and on Supabase rows). These are integration/regression
tests against the live system — slow and timing-sensitive, not unit tests.

> Unit tests (mocked Supabase + LLM) live in `bot/tests/` and run with `pytest`.
> They stay co-located with `bot/` because they import bot modules by bare name.

## Run — from the repo root

These scripts use **repo-root-relative paths** (`bot/.env`, the `learnix_tester` Telethon
session). Always launch them from the repository root so those paths resolve:

```bash
# from the repo root, NOT from inside tests/e2e
python tests/e2e/test_all.py            # full live regression sweep
python tests/e2e/test_struggle_live.py  # a single scenario
```

## Requirements

```bash
pip install -r tests/e2e/requirements.txt
```

Plus, in the repo root:
- `bot/.env` with `SUPABASE_URL`, `SUPABASE_KEY` (the scripts `load_dotenv("bot/.env")`).
- `learnix_tester.session` — a Telethon session for the tester account, created on first
  login. **Never commit it** (it holds auth secrets; gitignored as `*.session`).

## Notes

- After deploying, wait ~45s for the new container to swap before running these — early
  runs hit the old container and report stale results.
- Scripts create real DB rows; they clean up after themselves, but a crashed run can leave
  test data behind (the harness preserves the owner's real tasks, e.g. `Gym`).
