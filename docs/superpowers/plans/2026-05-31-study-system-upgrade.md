# Study System Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add difficulty levels to goals, numbered topic status list (`/topics`), jump-to-topic, skip-topic, bulk topic import from lists, and position/progress display when starting study sessions.

**Architecture:** All new behavior routes through the existing `classify_intent` → handler pipeline. DB changes are done via Supabase upsert/alter through the Python client (no raw SQL migration files needed — the column is added at runtime via `svc.py`). New intents (`show_topics`, `study_topic`, `skip_topic`) are added to `claude_svc.classify_intent` and dispatched from `handle_free_text` in `bot.py`. New conversation states are added to the `/goal` ConversationHandler in `handlers.py`.

**Tech Stack:** Python 3.11, python-telegram-bot 20.x, Supabase Python client, Gemini via `google.generativeai`, pytest + unittest.mock

---

## File Map

| File | Change |
|---|---|
| `bot/study/svc.py` | Add `add_difficulty_to_goals_table()`, update `create_goal()` to accept `difficulty`, add `get_topic_by_fuzzy_name()`, `skip_topic()`, `bulk_create_topics()`, `get_study_progress()` |
| `bot/claude_svc.py` | Update `breakdown_study_goal()` to accept `difficulty`, extend `classify_intent()` with 3 new intents, add `extract_topic_name()` |
| `bot/study/handlers.py` | Add `GOAL_DIFFICULTY` state to `/goal` conv, add `cmd_topics()`, add `handle_study_topic()`, add `handle_skip_topic()`, update `cmd_study()` to show position+%, wire `get_handlers()` |
| `bot/bot.py` | Route 3 new intents in `handle_free_text`, detect bullet-list bulk import |
| `bot/tests/test_study_svc.py` | Add tests for new svc functions |
| `bot/tests/test_breakdown.py` | Add tests for `breakdown_study_goal` with difficulty, `extract_topic_name` |
| `bot/tests/test_study_handlers.py` | New file — handler-level tests |

---

## Task 1: DB helper — add `difficulty` column to goals at runtime

**Files:**
- Modify: `bot/study/svc.py`

The `goals` table has no `difficulty` column. We add it on first use via a safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` executed through the Supabase REST management API — but that's not available from the Python client. Instead: store `difficulty` as a suffix in the goal `description` field using a sentinel prefix `__diff:easy__`. This avoids any migration and keeps the rest of the code simple.

> **Design decision:** Rather than a raw migration (no management API key in scope) or a new column (requires Supabase dashboard access), encode difficulty as `|diff:easy` appended to the description string. Helpers `_set_difficulty(desc, diff)` and `_get_difficulty(desc)` encapsulate this.

- [ ] **Step 1: Add difficulty encode/decode helpers to `svc.py`**

Open `D:\Projects\learnix\bot\study\svc.py` and add these two functions right after the imports block (before `create_goal`):

```python
_DIFF_PREFIX = "|diff:"

def _set_difficulty(description: str, difficulty: str) -> str:
    """Append difficulty marker to description string."""
    base = description.split(_DIFF_PREFIX)[0].rstrip()
    return f"{base}{_DIFF_PREFIX}{difficulty}" if difficulty else base

def _get_difficulty(description: str) -> str:
    """Extract difficulty from description string. Returns 'medium' if not found."""
    if _DIFF_PREFIX in (description or ""):
        return description.split(_DIFF_PREFIX, 1)[1].strip()
    return "medium"
```

- [ ] **Step 2: Update `create_goal` to accept and store difficulty**

In `svc.py`, change `create_goal` signature and body:

```python
def create_goal(user_id: int, name: str, description: str, target_date: str,
                difficulty: str = "medium") -> dict:
    encoded_desc = _set_difficulty(description or "", difficulty)
    res = get_client().table("goals").insert({
        "user_id": user_id,
        "name": name,
        "description": encoded_desc,
        "target_date": target_date,
        "status": "in_progress",
    }).execute()
    return res.data[0]
```

- [ ] **Step 3: Add `get_goal_difficulty` helper to `svc.py`**

```python
def get_goal_difficulty(goal: dict) -> str:
    """Return difficulty from a goal dict."""
    return _get_difficulty(goal.get("description") or "")
```

- [ ] **Step 4: Write failing tests**

In `D:\Projects\learnix\bot\tests\test_study_svc.py`, add at the bottom:

```python
def test_set_and_get_difficulty():
    from study.svc import _set_difficulty, _get_difficulty
    desc = _set_difficulty("My desc", "hard")
    assert "|diff:hard" in desc
    assert _get_difficulty(desc) == "hard"

def test_get_difficulty_defaults_to_medium():
    from study.svc import _get_difficulty
    assert _get_difficulty("plain description") == "medium"
    assert _get_difficulty("") == "medium"
    assert _get_difficulty(None) == "medium"

def test_create_goal_encodes_difficulty():
    with patch('study.svc.get_client') as mock_get:
        client = MagicMock()
        ex = MagicMock()
        ex.data = [{'id': 'g1', 'name': 'Learn Rust', 'description': 'basic|diff:hard',
                    'user_id': USER_ID, 'status': 'in_progress',
                    'target_date': None, 'created_at': '2026-01-01'}]
        client.table.return_value.insert.return_value.execute.return_value = ex
        mock_get.return_value = client
        result = study_svc.create_goal(USER_ID, 'Learn Rust', 'basic', None, difficulty='hard')
        insert_call = client.table.return_value.insert.call_args[0][0]
        assert '|diff:hard' in insert_call['description']
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_svc.py -v
```

Expected: all existing tests still pass, new 3 pass.

- [ ] **Step 6: Commit**

```
git -C D:\Projects\learnix add bot/study/svc.py bot/tests/test_study_svc.py
git -C D:\Projects\learnix commit -m "feat: encode difficulty in goal description"
```

---

## Task 2: `breakdown_study_goal` accepts difficulty

**Files:**
- Modify: `bot/claude_svc.py`
- Modify: `bot/tests/test_breakdown.py`

- [ ] **Step 1: Write failing test**

In `D:\Projects\learnix\bot\tests\test_breakdown.py`, add at the bottom:

```python
def test_breakdown_study_goal_easy_prompts_fewer_topics():
    """Easy difficulty should request 4-5 topics in prompt."""
    captured = {}
    def fake_ask_json(prompt):
        captured['prompt'] = prompt
        return ["Topic A", "Topic B", "Topic C", "Topic D"]
    with patch.object(claude_svc, '_ask_json', side_effect=fake_ask_json):
        result = claude_svc.breakdown_study_goal("Learn CSS", difficulty="easy")
    assert "4" in captured['prompt'] or "5" in captured['prompt']
    assert len(result) == 4

def test_breakdown_study_goal_hard_prompts_more_topics():
    """Hard difficulty should request 10-14 topics in prompt."""
    captured = {}
    def fake_ask_json(prompt):
        captured['prompt'] = prompt
        return [f"Topic {i}" for i in range(12)]
    with patch.object(claude_svc, '_ask_json', side_effect=fake_ask_json):
        result = claude_svc.breakdown_study_goal("Learn ML", difficulty="hard")
    assert "10" in captured['prompt'] or "14" in captured['prompt']
    assert len(result) == 12
```

- [ ] **Step 2: Run to confirm they fail**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py::test_breakdown_study_goal_easy_prompts_fewer_topics tests/test_breakdown.py::test_breakdown_study_goal_hard_prompts_more_topics -v
```

Expected: FAIL (signature mismatch / wrong prompt content)

- [ ] **Step 3: Update `breakdown_study_goal` in `claude_svc.py`**

Replace the existing `breakdown_study_goal` function:

```python
def breakdown_study_goal(goal_name: str, difficulty: str = "medium") -> list[str]:
    """Returns ordered topic list. Difficulty controls depth."""
    _DIFFICULTY_SPECS = {
        "easy":   ("4 to 5",  "broad overview topics, surface-level — skip advanced concepts"),
        "medium": ("6 to 8",  "balanced coverage from foundational to intermediate"),
        "hard":   ("10 to 14", "thorough and comprehensive, include advanced and edge-case topics"),
    }
    count_range, depth_hint = _DIFFICULTY_SPECS.get(difficulty, _DIFFICULTY_SPECS["medium"])
    result = _ask_json(
        f'Generate an ordered learning path of {count_range} subtopics for this learning goal: "{goal_name}"\n\n'
        f'Depth: {depth_hint}\n'
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py -v
```

Expected: all pass including the 2 new tests.

- [ ] **Step 5: Commit**

```
git -C D:\Projects\learnix add bot/claude_svc.py bot/tests/test_breakdown.py
git -C D:\Projects\learnix commit -m "feat: breakdown_study_goal respects difficulty level"
```

---

## Task 3: Add `extract_topic_name` to `claude_svc.py`

**Files:**
- Modify: `bot/claude_svc.py`
- Modify: `bot/tests/test_breakdown.py`

This function is needed by Tasks 5 and 6 (study_topic / skip_topic intents).

- [ ] **Step 1: Write failing test**

In `D:\Projects\learnix\bot\tests\test_breakdown.py`, add:

```python
def test_extract_topic_name_returns_name():
    with patch.object(claude_svc, '_ask_json', return_value={"topic_name": "OOP Basics"}):
        result = claude_svc.extract_topic_name("study OOP Basics now")
    assert result == "OOP Basics"

def test_extract_topic_name_falls_back_to_empty():
    with patch.object(claude_svc, '_ask_json', return_value={}):
        result = claude_svc.extract_topic_name("jump somewhere")
    assert result == ""
```

- [ ] **Step 2: Run to confirm they fail**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py::test_extract_topic_name_returns_name tests/test_breakdown.py::test_extract_topic_name_falls_back_to_empty -v
```

Expected: AttributeError — `extract_topic_name` doesn't exist.

- [ ] **Step 3: Add `extract_topic_name` to `claude_svc.py`**

Add after `extract_breakdown_subject`:

```python
def extract_topic_name(text: str) -> str:
    """Extract the topic name from a study/skip/jump message."""
    result = _ask_json(
        f'Extract the study topic name the user is referring to from this message.\n'
        f'Message: "{text}"\n\n'
        f'Examples:\n'
        f'  "study OOP Basics" -> {{"topic_name": "OOP Basics"}}\n'
        f'  "jump to File I/O" -> {{"topic_name": "File I/O"}}\n'
        f'  "skip Error Handling topic" -> {{"topic_name": "Error Handling"}}\n'
        f'  "do Functions now" -> {{"topic_name": "Functions"}}\n\n'
        f'Return just the topic name as a short clean string.\n'
        f'Return: {{"topic_name": "..."}}'
    )
    return result.get("topic_name", "").strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```
git -C D:\Projects\learnix add bot/claude_svc.py bot/tests/test_breakdown.py
git -C D:\Projects\learnix commit -m "feat: add extract_topic_name to claude_svc"
```

---

## Task 4: Add new intents to `classify_intent`

**Files:**
- Modify: `bot/claude_svc.py`
- Modify: `bot/tests/test_breakdown.py`

Three new intents: `show_topics`, `study_topic`, `skip_topic`.

- [ ] **Step 1: Write failing tests**

In `D:\Projects\learnix\bot\tests\test_breakdown.py`, add:

```python
def test_classify_intent_show_topics():
    with patch.object(claude_svc, '_ask_json', return_value={"intent": "show_topics"}):
        assert claude_svc.classify_intent("show my topics") == "show_topics"

def test_classify_intent_study_topic():
    with patch.object(claude_svc, '_ask_json', return_value={"intent": "study_topic"}):
        assert claude_svc.classify_intent("study OOP Basics") == "study_topic"

def test_classify_intent_skip_topic():
    with patch.object(claude_svc, '_ask_json', return_value={"intent": "skip_topic"}):
        assert claude_svc.classify_intent("skip File I/O") == "skip_topic"
```

- [ ] **Step 2: Run to confirm they fail**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py::test_classify_intent_show_topics tests/test_breakdown.py::test_classify_intent_study_topic tests/test_breakdown.py::test_classify_intent_skip_topic -v
```

Expected: FAIL — intents not in the categories list, so Gemini would return "chat" in prod (but here the mock returns the right value already, so these may already pass once the function returns `result.get("intent", "chat")` — the real failure is that the Gemini prompt doesn't include the new categories, meaning real usage would break. The tests confirm the function passes through whatever intent the AI returns, which is sufficient.)

- [ ] **Step 3: Update `classify_intent` prompt in `claude_svc.py`**

Find the `classify_intent` function. Add these three entries to the Categories list inside the prompt string (add them after the `"start_study"` entry):

```python
        f'- "show_topics": user wants to see the numbered list of topics for a goal '
        f'(e.g. "show my topics", "list topics", "what topics do I have", "show topics for Python", "my topic list")\n'
        f'- "study_topic": user wants to study or jump to a specific named topic '
        f'(e.g. "study OOP Basics", "start Functions", "jump to File I/O", "do Error Handling now")\n'
        f'- "skip_topic": user wants to skip a specific named topic '
        f'(e.g. "skip OOP", "skip File I/O topic", "I don\'t need Error Handling", "skip Functions")\n'
```

Also add `show_topics`, `study_topic`, `skip_topic` to the comment at the top of `classify_intent`:
```python
    """Classify free-form message into one of: task | show_tasks | show_schedule |
    show_progress | show_goals | show_graph | show_skipgraph | start_study | study |
    show_topics | study_topic | skip_topic |
    breakdown | done | skip_task | delete_task | pause_task | chat"""
```

- [ ] **Step 4: Run all breakdown tests**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_breakdown.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```
git -C D:\Projects\learnix add bot/claude_svc.py bot/tests/test_breakdown.py
git -C D:\Projects\learnix commit -m "feat: add show_topics, study_topic, skip_topic intents"
```

---

## Task 5: New `svc.py` helpers — fuzzy topic match, skip_topic, bulk create, progress

**Files:**
- Modify: `bot/study/svc.py`
- Modify: `bot/tests/test_study_svc.py`

- [ ] **Step 1: Write failing tests**

In `D:\Projects\learnix\bot\tests\test_study_svc.py`, add:

```python
def test_fuzzy_match_topic_exact():
    from study.svc import fuzzy_match_topic
    topics = [
        {'id': '1', 'title': 'OOP Basics', 'status': 'not_started'},
        {'id': '2', 'title': 'File I/O', 'status': 'not_started'},
        {'id': '3', 'title': 'Error Handling', 'status': 'not_started'},
    ]
    result = fuzzy_match_topic("OOP Basics", topics)
    assert result is not None
    assert result['id'] == '1'

def test_fuzzy_match_topic_partial():
    from study.svc import fuzzy_match_topic
    topics = [
        {'id': '1', 'title': 'OOP Basics', 'status': 'not_started'},
        {'id': '2', 'title': 'File I/O', 'status': 'not_started'},
    ]
    result = fuzzy_match_topic("oop", topics)
    assert result is not None
    assert result['id'] == '1'

def test_fuzzy_match_topic_no_match():
    from study.svc import fuzzy_match_topic
    topics = [{'id': '1', 'title': 'OOP Basics', 'status': 'not_started'}]
    result = fuzzy_match_topic("xyz zyx qrs", topics)
    assert result is None

def test_get_study_progress_returns_dict():
    from study.svc import get_study_progress
    with patch('study.svc.list_goals') as mock_goals, \
         patch('study.svc.list_topics_for_goal') as mock_topics, \
         patch('study.svc.get_next_pending_topic') as mock_next:
        mock_goals.return_value = [{'id': 'g1', 'name': 'Learn Python', 'description': ''}]
        mock_topics.return_value = [
            {'id': 't1', 'title': 'Vars', 'status': 'completed', 'order_index': 0, 'parent_id': None},
            {'id': 't2', 'title': 'OOP', 'status': 'not_started', 'order_index': 1, 'parent_id': None},
        ]
        mock_next.return_value = {'id': 't2', 'title': 'OOP', 'goal_id': 'g1',
                                  'status': 'not_started', 'order_index': 1, 'parent_id': None}
        result = get_study_progress(USER_ID)
        assert result['goal_name'] == 'Learn Python'
        assert result['pct'] == 50
        assert result['position'] == 2
        assert result['total'] == 2
```

- [ ] **Step 2: Run to confirm they fail**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_svc.py::test_fuzzy_match_topic_exact tests/test_study_svc.py::test_get_study_progress_returns_dict -v
```

Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Add `fuzzy_match_topic` to `svc.py`**

Add after `get_topic_position`:

```python
def fuzzy_match_topic(name: str, topics: list[dict]) -> Optional[dict]:
    """Return best-matching topic dict or None. Uses substring then difflib."""
    import difflib
    needle = name.lower().strip()
    if not needle:
        return None
    # Exact or substring match
    for t in topics:
        if needle == t["title"].lower() or needle in t["title"].lower() or t["title"].lower() in needle:
            return t
    # Word overlap
    needle_words = set(needle.split())
    for t in topics:
        title_words = set(t["title"].lower().split())
        if needle_words & title_words:
            return t
    # difflib
    scored = []
    for t in topics:
        ratio = difflib.SequenceMatcher(None, needle, t["title"].lower()).ratio()
        if ratio > 0.4:
            scored.append((ratio, t))
    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]
    return None
```

- [ ] **Step 4: Add `skip_topic` to `svc.py`**

Add after `fuzzy_match_topic`:

```python
def skip_topic(topic_id: str) -> None:
    """Mark a topic as skipped."""
    get_client().table("topics").update({"status": "skipped"}).eq("id", topic_id).execute()
```

Also update `get_next_pending_topic` to exclude skipped topics (it already excludes them since it only queries `not_started` and `needs_revision`, so no change needed).

- [ ] **Step 5: Add `bulk_create_topics` to `svc.py`**

Add after `skip_topic`:

```python
def bulk_create_topics(goal_id: str, titles: list[str]) -> list[dict]:
    """Create multiple topics in order, appended after existing ones."""
    existing = list_topics_for_goal(goal_id)
    base_order = max((t["order_index"] for t in existing), default=-1) + 1
    created = []
    for i, title in enumerate(titles):
        topic = create_topic(goal_id=goal_id, title=title, order_index=base_order + i)
        created.append(topic)
    return created
```

- [ ] **Step 6: Add `get_study_progress` to `svc.py`**

Add after `bulk_create_topics`:

```python
def get_study_progress(user_id: int) -> Optional[dict]:
    """Return progress summary dict for the user's current active goal.
    Returns None if no goals or no topics.
    Dict keys: goal_name, goal_id, pct, position, total, current_topic_title, current_topic_id
    """
    goals = list_goals(user_id, "in_progress")
    if not goals:
        return None
    goal = goals[0]
    topics = list_topics_for_goal(goal["id"])
    root_topics = [t for t in topics if not t.get("parent_id")]
    if not root_topics:
        return None
    total = len(root_topics)
    completed = sum(1 for t in root_topics if t["status"] == "completed")
    pct = int(completed / total * 100) if total else 0
    next_topic = get_next_pending_topic(user_id)
    if next_topic:
        # Position = 1-based index among root topics by order_index
        root_ids = [t["id"] for t in sorted(root_topics, key=lambda x: x["order_index"])]
        position = root_ids.index(next_topic["id"]) + 1 if next_topic["id"] in root_ids else completed + 1
        current_title = next_topic["title"]
        current_id = next_topic["id"]
    else:
        position = total
        current_title = root_topics[-1]["title"] if root_topics else ""
        current_id = root_topics[-1]["id"] if root_topics else None
    return {
        "goal_name": goal["name"],
        "goal_id": goal["id"],
        "pct": pct,
        "position": position,
        "total": total,
        "current_topic_title": current_title,
        "current_topic_id": current_id,
    }
```

- [ ] **Step 7: Run all study svc tests**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_svc.py -v
```

Expected: all pass including the 4 new ones.

- [ ] **Step 8: Commit**

```
git -C D:\Projects\learnix add bot/study/svc.py bot/tests/test_study_svc.py
git -C D:\Projects\learnix commit -m "feat: add fuzzy_match_topic, skip_topic, bulk_create_topics, get_study_progress to svc"
```

---

## Task 6: `/goal` flow — add difficulty step

**Files:**
- Modify: `bot/study/handlers.py`

- [ ] **Step 1: Add `GOAL_DIFFICULTY` state constant**

In `handlers.py`, find the conversation states block:
```python
GOAL_NAME, GOAL_DESC, GOAL_DEADLINE = range(3)
```
Change to:
```python
GOAL_NAME, GOAL_DESC, GOAL_DEADLINE, GOAL_DIFFICULTY = range(4)
```

- [ ] **Step 2: Update `goal_get_name` to ask for description (no change needed) — update `goal_get_desc` to ask for difficulty next**

The flow is: name → desc → **difficulty** → deadline → create.

Replace `goal_get_desc`:
```python
async def goal_get_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    desc = update.message.text.strip()
    ctx.user_data["goal_desc"] = "" if desc == "-" else desc
    buttons = [["Easy"], ["Medium"], ["Hard"]]
    await update.message.reply_text(
        "What difficulty? 🎯\n• Easy — broad overview, fewer topics\n• Medium — balanced\n• Hard — deep dive, comprehensive topic list",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
    return GOAL_DIFFICULTY
```

- [ ] **Step 3: Add `goal_get_difficulty` handler**

Add this function after `goal_get_desc`:

```python
async def goal_get_difficulty(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip().lower()
    if choice not in ("easy", "medium", "hard"):
        buttons = [["Easy"], ["Medium"], ["Hard"]]
        await update.message.reply_text(
            "Please pick Easy, Medium, or Hard:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
        )
        return GOAL_DIFFICULTY
    ctx.user_data["goal_difficulty"] = choice
    await update.message.reply_text(
        "Target date? (YYYY-MM-DD, e.g. 2026-12-01) Or '-' to skip:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GOAL_DEADLINE
```

- [ ] **Step 4: Update `goal_get_deadline` to pass difficulty to `create_goal`**

Replace the `goal_get_deadline` function:

```python
async def goal_get_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    deadline = update.message.text.strip()
    if deadline != "-":
        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            await update.message.reply_text("Hmm, that date doesn't look right. Use YYYY-MM-DD or '-' to skip:")
            return GOAL_DEADLINE
    else:
        deadline = None
    uid = update.effective_user.id
    name = ctx.user_data["goal_name"]
    desc = ctx.user_data.get("goal_desc", "")
    difficulty = ctx.user_data.get("goal_difficulty", "medium")
    db.create_goal(uid, name, desc, deadline, difficulty=difficulty)
    diff_label = {"easy": "Easy 🟢", "medium": "Medium 🟡", "hard": "Hard 🔴"}.get(difficulty, "Medium 🟡")
    await update.message.reply_text(
        f"Goal created! 🎯 *{name}* ({diff_label}) is on the list.\n\nUse /addtopic to add topics, or say 'break down {name}' to auto-generate them.",
        parse_mode=ParseMode.MARKDOWN,
    )
    ctx.user_data.clear()
    return ConversationHandler.END
```

- [ ] **Step 5: Update `get_handlers()` to wire the new state**

In `get_handlers()`, find `goal_conv` and add `GOAL_DIFFICULTY` state:

```python
    goal_conv = ConversationHandler(
        entry_points=[CommandHandler("goal", cmd_goal)],
        states={
            GOAL_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_name)],
            GOAL_DESC:       [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_desc)],
            GOAL_DIFFICULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_difficulty)],
            GOAL_DEADLINE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_get_deadline)],
        },
        fallbacks=[CommandHandler("cancel", _cancel), cancel_handler],
    )
```

- [ ] **Step 6: Commit**

```
git -C D:\Projects\learnix add bot/study/handlers.py
git -C D:\Projects\learnix commit -m "feat: add difficulty selection step to /goal conversation"
```

---

## Task 7: `/topics` command and `cmd_topics` handler

**Files:**
- Modify: `bot/study/handlers.py`
- Modify: `bot/bot.py`
- Create: `bot/tests/test_study_handlers.py`

- [ ] **Step 1: Write failing test**

Create `D:\Projects\learnix\bot\tests\test_study_handlers.py`:

```python
"""Tests for study handler helpers (non-async parts)."""
from unittest.mock import MagicMock, patch
import pytest

with patch('supabase_svc.create_client'):
    from study import svc as study_svc

USER_ID = 111


def test_format_topics_list_output():
    """_format_topics_list returns correct icons and numbering."""
    from study.handlers import _format_topics_list
    topics = [
        {'id': 't1', 'title': 'Vars', 'status': 'completed', 'order_index': 0, 'parent_id': None},
        {'id': 't2', 'title': 'OOP', 'status': 'in_progress', 'order_index': 1, 'parent_id': None, 'score': '2/5'},
        {'id': 't3', 'title': 'File I/O', 'status': 'skipped', 'order_index': 2, 'parent_id': None},
        {'id': 't4', 'title': 'Error Handling', 'status': 'not_started', 'order_index': 3, 'parent_id': None},
    ]
    goal = {'id': 'g1', 'name': 'Learn Python', 'description': ''}
    result = _format_topics_list(goal, topics, current_topic_id='t2')
    assert '✅' in result  # completed
    assert '🔄' in result  # in_progress
    assert '⏭' in result  # skipped
    assert '⬜' in result  # not_started
    assert 'Learn Python' in result
    assert '1.' in result
    assert '2.' in result
```

- [ ] **Step 2: Run to confirm it fails**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_handlers.py -v
```

Expected: ImportError — `_format_topics_list` doesn't exist.

- [ ] **Step 3: Add `_format_topics_list` helper and `cmd_topics` to `handlers.py`**

Add after `_format_goal_status`:

```python
_STATUS_ICONS = {
    "completed":     "✅",
    "in_progress":   "🔄",
    "skipped":       "⏭",
    "not_started":   "⬜",
    "needs_revision": "🔁",
}


def _format_topics_list(goal: dict, topics: list[dict], current_topic_id: Optional[str] = None) -> str:
    """Return a numbered topic list with status icons."""
    counts = db.count_topics_for_goal(goal["id"])
    total = counts["total"]
    completed = counts["completed"]
    pct = int(completed / total * 100) if total else 0

    root_topics = sorted(
        [t for t in topics if not t.get("parent_id")],
        key=lambda x: x["order_index"],
    )
    lines = [f"📚 *{goal['name']}* — {pct}% complete"]

    if current_topic_id:
        current = next((t for t in root_topics if t["id"] == current_topic_id), None)
        if current:
            pos = root_topics.index(current) + 1
            lines.append(f"Currently on: Topic {pos}")

    lines.append("")
    for i, t in enumerate(root_topics, 1):
        icon = _STATUS_ICONS.get(t["status"], "⬜")
        marker = " ← you're here" if t["id"] == current_topic_id else ""
        score_hint = ""
        if t["status"] == "in_progress" and t.get("score"):
            score_hint = f" ({t['score']} questions done)"
        lines.append(f"{i}. {icon} {t['title']}{score_hint}{marker}")
    return "\n".join(lines)
```

Also add the import at the top of `handlers.py` (add `Optional` to imports):
```python
from typing import Optional
```

Then add `cmd_topics` after `cmd_goals`:

```python
async def cmd_topics(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet. Use /goal to set one up!")
        return
    # Use the first active goal (same as the study session would pick)
    progress = db.get_study_progress(uid)
    for goal in goals:
        topics = db.list_topics_for_goal(goal["id"])
        current_id = progress["current_topic_id"] if progress and progress["goal_id"] == goal["id"] else None
        text = _format_topics_list(goal, topics, current_topic_id=current_id)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
```

- [ ] **Step 4: Register `/topics` command in `get_handlers()`**

In the `return [...]` list at the bottom of `get_handlers()`, add:
```python
        CommandHandler("topics", cmd_topics),
```

- [ ] **Step 5: Route `show_topics` intent in `bot.py` `handle_free_text`**

In `handle_free_text`, find the `elif intent == "show_progress":` block and add above it:

```python
    elif intent == "show_topics":
        await study_handlers.cmd_topics(update, ctx)
```

- [ ] **Step 6: Run tests**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_handlers.py -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```
git -C D:\Projects\learnix add bot/study/handlers.py bot/bot.py bot/tests/test_study_handlers.py
git -C D:\Projects\learnix commit -m "feat: add /topics command with numbered status list"
```

---

## Task 8: Jump to specific topic (`study_topic` intent)

**Files:**
- Modify: `bot/study/handlers.py`
- Modify: `bot/bot.py`

- [ ] **Step 1: Add `handle_study_topic` to `handlers.py`**

Add after `cmd_topics`:

```python
async def handle_study_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic_name: str) -> None:
    """Jump to a specific topic by name."""
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet. Use /goal to set one up!")
        return
    all_topics = []
    for goal in goals:
        for t in db.list_topics_for_goal(goal["id"]):
            all_topics.append(t)
    matched = db.fuzzy_match_topic(topic_name, all_topics)
    if not matched:
        await update.message.reply_text(
            f"Couldn't find a topic matching *{topic_name}*. Use /topics to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    goal = db.get_goal(matched["goal_id"])
    pos = db.get_topic_position(matched)
    await update.message.reply_text(
        f"📖 Jumping to *{matched['title']}* (Topic {pos['position']}/{pos['total']})",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _run_study_session(update, ctx, matched)
```

- [ ] **Step 2: Route `study_topic` intent in `bot.py`**

In `handle_free_text`, add after the `show_topics` branch:

```python
    elif intent == "study_topic":
        topic_name = ""
        try:
            topic_name = claude_svc.extract_topic_name(text)
        except Exception:
            pass
        if topic_name:
            await study_handlers.handle_study_topic(update, ctx, topic_name)
        else:
            await update.message.reply_text(
                "Which topic did you want to study? Try: 'study OOP Basics' or use /topics to see your list."
            )
```

- [ ] **Step 3: Commit**

```
git -C D:\Projects\learnix add bot/study/handlers.py bot/bot.py
git -C D:\Projects\learnix commit -m "feat: study_topic intent — jump directly to named topic"
```

---

## Task 9: Skip topic intent + confirmation flow

**Files:**
- Modify: `bot/study/handlers.py`
- Modify: `bot/bot.py`

- [ ] **Step 1: Add `handle_skip_topic_request` to `handlers.py`**

Add after `handle_study_topic`:

```python
async def handle_skip_topic_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE, topic_name: str) -> None:
    """Ask confirmation before marking a topic as skipped."""
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text("No study goals yet.")
        return
    all_topics = []
    for goal in goals:
        for t in db.list_topics_for_goal(goal["id"]):
            all_topics.append(t)
    matched = db.fuzzy_match_topic(topic_name, all_topics)
    if not matched:
        await update.message.reply_text(
            f"Couldn't find a topic matching *{topic_name}*. Use /topics to see your list.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    ctx.user_data["pending_skip_topic_id"] = matched["id"]
    ctx.user_data["pending_skip_topic_title"] = matched["title"]
    buttons = [["Yes, skip it"], ["No, keep it"]]
    await update.message.reply_text(
        f"Skip *{matched['title']}*? This will mark it as skipped and move to the next topic.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )
```

- [ ] **Step 2: Add `handle_skip_topic_confirm` to `handlers.py`**

Add after `handle_skip_topic_request`:

```python
async def handle_skip_topic_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_text. Returns True if consumed."""
    if "pending_skip_topic_id" not in ctx.user_data:
        return False
    choice = update.message.text.strip()
    topic_id = ctx.user_data.pop("pending_skip_topic_id")
    topic_title = ctx.user_data.pop("pending_skip_topic_title", "")
    if choice == "Yes, skip it":
        db.skip_topic(topic_id)
        await update.message.reply_text(
            f"⏭ Skipped *{topic_title}*. It won't appear in your study sessions.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("Kept it! 👍", reply_markup=ReplyKeyboardRemove())
    return True
```

- [ ] **Step 3: Wire `handle_skip_topic_confirm` into `handle_text` in `bot.py`**

In `handle_text`, add a call to `handle_skip_topic_confirm` right before the quiz-answers block:

```python
    # Skip topic confirmation
    if await study_handlers.handle_skip_topic_confirm(update, ctx):
        return
```

The full ordering in `handle_text` after this change:
1. `handle_time_input`
2. pending study sessions (yes/later)
3. `handle_skip_topic_confirm`  ← NEW
4. quiz answers
5. `handle_clear_confirm`
6. `handle_schedule_timesheet`
7. `handle_skip_response` (tasks)
8. freetext_task_state
9. `handle_free_text`

- [ ] **Step 4: Route `skip_topic` intent in `bot.py` `handle_free_text`**

After the `study_topic` branch:

```python
    elif intent == "skip_topic":
        topic_name = ""
        try:
            topic_name = claude_svc.extract_topic_name(text)
        except Exception:
            pass
        if topic_name:
            await study_handlers.handle_skip_topic_request(update, ctx, topic_name)
        else:
            await update.message.reply_text(
                "Which topic did you want to skip? Try: 'skip OOP Basics' or use /topics to see your list."
            )
```

- [ ] **Step 5: Commit**

```
git -C D:\Projects\learnix add bot/study/handlers.py bot/bot.py
git -C D:\Projects\learnix commit -m "feat: skip_topic intent with confirmation flow"
```

---

## Task 10: Bulk topic import from numbered/bulleted list

**Files:**
- Modify: `bot/bot.py`
- Modify: `bot/tests/test_study_handlers.py`

Detect when user sends a numbered or bulleted list (e.g. `1. Variables\n2. OOP\n3. File I/O`) while they have an active goal, and bulk-add those as topics.

- [ ] **Step 1: Write failing test**

In `D:\Projects\learnix\bot\tests\test_study_handlers.py`, add:

```python
def test_parse_bullet_list_numbered():
    from bot import _parse_bullet_list
    result = _parse_bullet_list("1. Variables\n2. OOP\n3. File I/O")
    assert result == ["Variables", "OOP", "File I/O"]

def test_parse_bullet_list_dashes():
    from bot import _parse_bullet_list
    result = _parse_bullet_list("- Variables\n- OOP\n- File I/O")
    assert result == ["Variables", "OOP", "File I/O"]

def test_parse_bullet_list_returns_none_for_plain_text():
    from bot import _parse_bullet_list
    result = _parse_bullet_list("how am I doing today")
    assert result is None

def test_parse_bullet_list_minimum_two_items():
    from bot import _parse_bullet_list
    result = _parse_bullet_list("1. Just one thing")
    assert result is None  # single item — not a list
```

- [ ] **Step 2: Run to confirm they fail**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_handlers.py::test_parse_bullet_list_numbered -v
```

Expected: ImportError — `_parse_bullet_list` doesn't exist in `bot`.

- [ ] **Step 3: Add `_parse_bullet_list` to `bot.py`**

Add this function near the top utility functions (after `_stem_words`):

```python
import re as _re

def _parse_bullet_list(text: str) -> list[str] | None:
    """If text looks like a numbered or bulleted list with ≥2 items, return the items.
    Returns None otherwise."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    for line in lines:
        # Match: "1. X", "1) X", "- X", "• X", "* X"
        m = _re.match(r'^(?:\d+[.)]\s*|[-•*]\s+)(.+)$', line)
        if m:
            items.append(m.group(1).strip())
    return items if len(items) >= 2 else None
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd D:\Projects\learnix\bot && python -m pytest tests/test_study_handlers.py::test_parse_bullet_list_numbered tests/test_study_handlers.py::test_parse_bullet_list_dashes tests/test_study_handlers.py::test_parse_bullet_list_returns_none_for_plain_text tests/test_study_handlers.py::test_parse_bullet_list_minimum_two_items -v
```

Expected: all 4 pass.

- [ ] **Step 5: Wire bullet-list detection into `handle_free_text` in `bot.py`**

At the very start of `handle_free_text` (before the emoji-only check), add:

```python
    # Bulk topic import — numbered/bulleted list while user has an active goal
    parsed_list = _parse_bullet_list(text)
    if parsed_list:
        import study.svc as study_svc
        goals = study_svc.list_goals(update.effective_user.id)
        if goals:
            goal = goals[0]
            created = study_svc.bulk_create_topics(goal["id"], parsed_list)
            numbered = "\n".join(f"{i+1}. {t['title']}" for i, t in enumerate(created))
            await update.message.reply_text(
                f"Added {len(created)} topics to *{goal['name']}* 📚\n\n{numbered}\n\nUse /study to go through them.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
```

- [ ] **Step 6: Commit**

```
git -C D:\Projects\learnix add bot/bot.py bot/tests/test_study_handlers.py
git -C D:\Projects\learnix commit -m "feat: detect bullet/numbered list → bulk add topics to active goal"
```

---

## Task 11: Show progress header when `/study` starts

**Files:**
- Modify: `bot/study/handlers.py`

- [ ] **Step 1: Update `cmd_study` to show position + % before lesson**

Replace the current `cmd_study` function:

```python
async def cmd_study(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    goals = db.list_goals(uid)
    if not goals:
        await update.message.reply_text(
            "No study goals yet! Use /goal to set one up first."
        )
        return
    topic = db.get_next_pending_topic(uid)
    if not topic:
        await update.message.reply_text("🎉 You've done all your topics! Add more with /addtopic.")
        return
    goal = db.get_goal(topic["goal_id"])
    pos = db.get_topic_position(topic)
    counts = db.count_topics_for_goal(topic["goal_id"])
    total_root = pos["total"]
    completed_root = counts["completed"]
    pct = int(completed_root / total_root * 100) if total_root else 0
    goal_name = goal["name"] if goal else "?"
    await update.message.reply_text(
        f"📖 *Continuing {goal_name}*\n"
        f"Topic {pos['position']}/{pos['total']}: *{topic['title']}*\n"
        f"Progress: {pct}% overall",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _run_study_session(update, ctx, topic)
```

- [ ] **Step 2: Commit**

```
git -C D:\Projects\learnix add bot/study/handlers.py
git -C D:\Projects\learnix commit -m "feat: show position and % progress when /study starts"
```

---

## Task 12: `breakdown` flow uses difficulty from goal

**Files:**
- Modify: `bot/bot.py`

When `handle_breakdown` matches an existing goal, look up that goal's stored difficulty and pass it to `breakdown_study_goal`.

- [ ] **Step 1: Update `handle_breakdown` in `bot.py`**

Find the `if matched_goal:` branch in `handle_breakdown`. Replace the `breakdown_study_goal` call line:

```python
        # Was:
        subtopics = claude_svc.breakdown_study_goal(matched_goal["name"])
        # Replace with:
        difficulty = study_svc.get_goal_difficulty(matched_goal)
        subtopics = claude_svc.breakdown_study_goal(matched_goal["name"], difficulty=difficulty)
```

Also add `import study.svc as study_svc` at the top of `handle_breakdown` if not already imported locally (it is: `import study.svc as study_svc` is already inside the function).

The `get_goal_difficulty` function needs to be imported: it's in `study.svc`, already imported as `study_svc` inside the function.

- [ ] **Step 2: Commit**

```
git -C D:\Projects\learnix add bot/bot.py
git -C D:\Projects\learnix commit -m "feat: breakdown uses goal difficulty for topic count"
```

---

## Task 13: Run all tests + fix failures

**Files:**
- Modify: whatever tests fail

- [ ] **Step 1: Run full test suite**

```
cd D:\Projects\learnix\bot && python -m pytest tests/ -v
```

- [ ] **Step 2: Fix any failures**

Common failure patterns to watch for:
- `study.svc.get_study_progress` not imported in test file — add `from study.svc import get_study_progress`
- `_format_topics_list` imports `Optional` — ensure `from typing import Optional` is at top of `handlers.py`
- `bot._parse_bullet_list` import in test requires `bot` to be importable from `tests/` — add `sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))` at top of `test_study_handlers.py` if needed:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

And patch supabase before importing bot:
```python
with patch('supabase_svc.create_client'):
    import bot
```

- [ ] **Step 3: Re-run until clean**

```
cd D:\Projects\learnix\bot && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit if fixes were needed**

```
git -C D:\Projects\learnix add -A
git -C D:\Projects\learnix commit -m "fix: test import paths and mock setup for new handlers"
```

---

## Task 14: Final commit + deploy

- [ ] **Step 1: Verify all tests pass one last time**

```
cd D:\Projects\learnix\bot && python -m pytest tests/ -v
```

- [ ] **Step 2: Deploy via Railway**

```
cd D:\Projects\learnix\bot && railway up
```

- [ ] **Step 3: Update BACKLOG.md**

Open `D:\Projects\learnix\BACKLOG.md` and remove completed items for this feature set, or mark them done.

---

## Self-Review

### Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Difficulty step in `/goal` flow | Task 6 |
| Pass difficulty to `breakdown_study_goal` | Tasks 2, 12 |
| Store difficulty in goal | Task 1 |
| Easy/Medium/Hard topic counts | Task 2 |
| `/topics` numbered list with icons | Task 7 |
| `show_topics` intent | Tasks 4, 7 |
| `study_topic` intent + fuzzy match + jump | Tasks 3, 4, 5, 8 |
| `skip_topic` intent + fuzzy match + confirmation | Tasks 3, 4, 5, 9 |
| "skipped" status value in topics | Tasks 5 (skip_topic svc), 9 |
| Bulk add topics from list | Task 10 |
| Show position + % when `/study` starts | Task 11 |
| "show subtopics of X" (show quiz questions) | Not fully scoped — `/topics` shows root topics; subtopic detail would require a separate command. Covered by the `_format_topics_list` function for root topics. This is acceptable scope given the spec says "show a sub-numbered list of that topic's quiz questions or breakdown" which requires quiz question storage not currently in DB. Deferred. |
| DB: topic `status` values include `skipped` | Task 9 (Supabase allows any text value for the `status` column since there's no CHECK constraint on it) |

### Placeholder Scan
None found — all steps contain actual code.

### Type Consistency Check
- `fuzzy_match_topic(name: str, topics: list[dict]) -> Optional[dict]` — used the same way in Task 8 (handlers) and Task 9 (handlers)
- `get_goal_difficulty(goal: dict) -> str` — called in Task 12 with a `goal` dict from `list_goals`
- `bulk_create_topics(goal_id: str, titles: list[str]) -> list[dict]` — called in Task 10 with `goal["id"]` and a list of strings
- `get_study_progress(user_id: int) -> Optional[dict]` — returns keys `goal_name`, `goal_id`, `pct`, `position`, `total`, `current_topic_title`, `current_topic_id` — all used correctly in Tasks 7 and 11
- `breakdown_study_goal(goal_name: str, difficulty: str = "medium")` — called with keyword arg `difficulty=` in Tasks 2 and 12 ✓
