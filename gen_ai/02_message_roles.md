# Module 2: Message Structure & Roles

## Notes
- The messages array has three roles: **system**, **user**, **assistant**
- **system** — global instruction, sets rules, tone, format, persona. Highest priority.
- **user** — the human's input or task for this turn
- **assistant** — the model's previous replies (included manually to maintain context)
- Order matters: messages are read top to bottom
- Including past assistant replies in the prompt is how you fake "memory" across turns

**Key takeaway:** The system message defines rules; user messages drive the task; assistant messages preserve context. All three must be managed by the developer.

---

## Quiz
Q1. (MCQ) Which role sets the overall behavior, tone, and rules for the model?
    a) user
    b) assistant
    c) system
    d) context

Q2. If you want the model to remember what it said in a previous turn, what must you do?

Q3. (MCQ) In what order are messages typically structured in an API call?
    a) user → system → assistant
    b) assistant → user → system
    c) system → user → assistant (alternating)
    d) Any order, it doesn't matter

Q4. What happens if you completely omit the system message?

Q5. You're building a customer support bot. Write a one-line system message that would make the model respond only in formal English and never discuss topics outside of product support.

---

## Answers
A1. c) system

A2. You must include the previous assistant reply as a message with role "assistant" in the messages array of the next API call. The model doesn't store it automatically.

A3. c) system → user → assistant (alternating). Typically: system first, then user/assistant turns alternating.

A4. The model uses its default behavior — no specific persona, tone, or rules enforced. Output can be inconsistent or not suited to your use case.

A5. Example: "You are a formal customer support agent. Only answer questions related to our products. Do not discuss any other topics."

---

## Result
Date: 2026-04-04
Score: PENDING
Status: PENDING
