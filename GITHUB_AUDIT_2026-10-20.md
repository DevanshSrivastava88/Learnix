# GitHub audit 2026-10-20 - Learnix
- **Verdict: SAFE**
- Remote: https://github.com/DevanshSrivastava88/Learnix.git

| Check | Result |
|---|---|
| Unpushed commits (clone) | none |
| Uncommitted/untracked (clone) | none |
| Local-only secrets (names only) | rescue: learnix/bot/.env, web/.env.local (not in clone, in D_rescue only) |
| In D_rescue but NOT on GitHub | None. Rescue branches (38 master + admin-bypass cmds) all exist on GitHub by subject (history was scrubbed so hashes differ) |
| Fix | Copy those .env to Bitwarden |
