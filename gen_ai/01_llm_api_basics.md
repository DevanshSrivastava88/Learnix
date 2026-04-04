# Module 1: LLM API Basics

## Notes
- An LLM call is a remote API request — you send structured JSON, get structured JSON back
- You send: model name, messages array, parameters
- You receive: a completion (predicted tokens)
- The model does NOT think or store memory — it predicts the next token by probability
- Each API call is completely independent (stateless)
- All behavior must be provided in the prompt — the model has no state of its own

**Key takeaway:** LLMs are stateless function calls. All context and behavior must be supplied every time.

---

## Quiz
Q1. (MCQ) What does an LLM API call return?
    a) A trained model update
    b) Structured JSON with the model's predicted output
    c) A database record
    d) A memory snapshot

Q2. What does "stateless" mean in the context of LLM API calls?

Q3. (MCQ) What three things do you typically send in an LLM API request?
    a) Model name, messages, parameters
    b) Model name, memory, instructions
    c) Prompt, database, temperature
    d) Token, context, weight

Q4. Does the LLM "understand" your question the way a human does? Explain briefly.

Q5. If you make two separate API calls, does the model remember the first call in the second? Why or why not?

---

## Answers
A1. b) Structured JSON with the model's predicted output

A2. Stateless means each API call is independent — the model has no memory of previous calls. Every call starts fresh with only what you send in that request.

A3. a) Model name, messages, parameters

A4. No. The LLM predicts the most probable next tokens based on patterns learned during training. It doesn't "understand" — it statistically completes the input.

A5. No. Each call is independent. The model only sees what's in the current request. To carry context forward, you must include previous messages in the next call yourself.

---

## Result
Date: 2026-04-04
Score: PENDING
Status: PENDING
