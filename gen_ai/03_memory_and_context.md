# Module 3: Memory — Stateless vs Context Window

## Notes
- A raw LLM API call has **no memory across calls** — each call is fully independent
- Within a single API call, the **context window** holds all included messages
- The model can reference anything in the current context window
- Context window has a **token limit** — you can't include infinite history
- All "memory" is controlled by the developer — you decide what to include each call
- Types of memory in LLM systems:
  - **No memory** — each call is fresh (default)
  - **Temporary memory** — pass conversation history in the prompt (context window)
  - **Persistent memory** — store history externally (DB, file) and inject it back

| Feature | Raw LLM (Stateless) | LLM + Context Window |
|---|---|---|
| Memory across calls | None | Only what you include |
| Memory scope | Current input only | All messages in this call |
| Who controls it | Developer re-sends context | Developer includes past messages |

**Key takeaway:** The model forgets everything not in the current request. Memory is an illusion created by passing history back in the prompt.

---

## Quiz
Q1. (MCQ) What happens to conversation history after a raw LLM API call ends?
    a) It's saved automatically in the model
    b) It's stored in the cloud
    c) It's forgotten — the next call starts fresh
    d) It's cached for 24 hours

Q2. What is the context window?

Q3. (MCQ) What limits how much conversation history you can include in a single call?
    a) The API key
    b) The token limit of the context window
    c) The number of messages
    d) The model version

Q4. You're building a chatbot that needs to remember the last 10 messages. How would you implement this with a raw LLM API?

Q5. What is the difference between "temporary memory" and "persistent memory" in LLM systems?

---

## Answers
A1. c) It's forgotten — the next call starts fresh

A2. The context window is the total amount of text (measured in tokens) that a model can process in a single API call. It includes the system message, all user and assistant turns, and the response.

A3. b) The token limit of the context window

A4. You maintain a list of the last 10 message objects (role + content) in your application. On each new call, you include those 10 messages in the messages array along with the new user message.

A5. Temporary memory = conversation history included in the current prompt (lost when the session ends). Persistent memory = history saved to an external store (database, file) and re-injected into future calls — survives across sessions.

---

## Result
Date: 2026-04-04
Score: PENDING
Status: PENDING
