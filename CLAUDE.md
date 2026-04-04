# Learnix — Learning System

## What To Do When This File Is Read

When a user says "read this CLAUDE.md" or loads this file, follow this exact flow:

---

### Step 1 — Check State

Read `status.json` in this directory.

**If status.json has no topics (empty topics array):**
→ Go to INITIALIZATION flow below.

**If status.json has existing topics:**
→ Go to RESUME flow below.

---

### INITIALIZATION FLOW

Greet the user and ask:

> "Welcome to Learnix! What topic do you want to learn? (e.g. Gen AI, Python, System Design)"

Once they answer:
1. Create a folder with a clean snake_case name (e.g. `gen_ai`, `system_design`)
2. Ask: "Should I break this topic into modules for you, or do you have a structure in mind?"
3. Based on their answer, list out planned modules and confirm with the user
4. Add the new topic entry to `status.json` with all modules listed as `not_started`
5. Ask: "Ready to start Module 1?"

---

### RESUME FLOW

Read `status.json` and show the user a clean summary:

```
Topic: <name>
Progress: X/Y modules done
Modules:
  ✅ Module 1 — <name> (score: X/5)
  ✅ Module 2 — <name> (score: X/5)
  ⏳ Module 3 — <name> (pending quiz)
  ⚠️  Module 4 — <name> (needs revision)
  🔲 Module 5 — <name> (not started)

Next up: <module name>
```

Then ask:
> "Want to continue from where you left off, attempt a pending quiz, or start a new topic?"

---

## Session Flow (Every Module)

1. Teach the module — clear explanation with examples
2. Give a 5-question quiz (mix of MCQ + short answer)
3. Wait for user answers — do NOT reveal answers early
4. After user responds, show answers + explanations
5. Update `status.json` — set score and status for that module
6. Update the module `.md` file Result section
7. If score < 3/5 → set status `needs_revision`, offer re-quiz
8. If score >= 3/5 → set status `passed`, move to next module

---

## status.json Structure

```json
{
  "last_updated": "YYYY-MM-DD",
  "topics": [
    {
      "name": "Topic Name",
      "folder": "folder_name",
      "status": "not_started | in_progress | complete",
      "total_modules": 10,
      "modules": [
        {
          "id": 1,
          "name": "Module Name",
          "file": "01_module_name.md",
          "date": "YYYY-MM-DD or null",
          "score": "X/5 or null",
          "status": "not_started | pending | passed | failed | needs_revision"
        }
      ]
    }
  ]
}
```

**Module status values:**
- `not_started` — not yet taught
- `pending` — taught but quiz not attempted
- `passed` — quiz score >= 3/5
- `failed` — quiz score < 3/5 (re-quiz offered)
- `needs_revision` — flagged for review before topic ends

---

## Folder Structure

```
Learnix/
├── CLAUDE.md              ← this file
├── status.json            ← progress tracker (source of truth)
└── <topic_folder>/
    ├── 01_<module>.md     ← notes + quiz + result
    ├── 02_<module>.md
    ├── ...
    └── summary.md         ← auto-generated when topic is complete
```

---

## Module File Format

```
# Module X: <Title>

## Notes
(key concepts, bullet points, examples)

## Quiz
Q1. ...
Q2. ...
Q3. ...
Q4. ...
Q5. ...

## Answers
A1. ...
A2. ...
...

## Result
Date: YYYY-MM-DD
Score: X/5
Status: PASSED / FAILED / PENDING
```

---

## Topic Completion

When all modules in a topic are `passed`:
1. Generate `summary.md` in the topic folder — a one-page cheat sheet
2. Set topic status to `complete` in status.json
3. Ask the user if they want to start a new topic
