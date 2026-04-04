# Module 4: System Message Power

## Notes
- The system message is the **highest-level instruction** — it governs everything that follows
- A precise system message produces deterministic, predictable output
- A vague or contradictory system message leads to inconsistent behavior
- Use cases for system messages:
  - Enforce output format (e.g. "Always respond in JSON with this schema")
  - Set persona (e.g. "You are a senior Python engineer")
  - Set constraints (e.g. "Never discuss competitors")
  - Set tone (e.g. "Always respond formally")
- The more specific and unambiguous, the better
- Conflicting instructions (e.g. "Be concise" + "Explain everything in detail") cause unpredictable output

**Key takeaway:** Treat the system message like a contract. It must be precise, unambiguous, and non-contradictory to reliably shape model behavior.

---

## Quiz
Q1. (MCQ) What is the role of the system message in an LLM API call?
    a) It provides the user's question
    b) It stores the model's memory
    c) It sets the highest-level rules and behavior for the model
    d) It defines the API endpoint

Q2. You want the model to always return a JSON object with keys "name" and "score". Write a system message that enforces this.

Q3. (MCQ) What happens when you give the model a vague or contradictory system message?
    a) The API throws an error
    b) The model ignores the system message
    c) Output becomes inconsistent and unpredictable
    d) The model uses default behavior and ignores all instructions

Q4. Why is the system message considered "higher priority" than the user message?

Q5. Give one example of a contradictory system message and explain why it causes problems.

---

## Answers
A1. c) It sets the highest-level rules and behavior for the model

A2. Example: "You are a data extraction assistant. Always respond with a valid JSON object containing exactly two keys: 'name' (string) and 'score' (number). Do not include any other text outside the JSON."

A3. c) Output becomes inconsistent and unpredictable

A4. The system message is read first and establishes the frame for the entire conversation. User messages operate within the constraints set by the system message — the model is instructed to treat system-level rules as non-negotiable.

A5. Example: "Be extremely concise. Also make sure to explain every concept thoroughly with multiple examples." — These two instructions directly conflict. The model can't be both concise and exhaustively detailed, so it will inconsistently toggle between behaviors.

---

## Result
Date: 2026-04-04
Score: PENDING
Status: PENDING
