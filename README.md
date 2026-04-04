# Learnix

A personal learning system powered by Claude. Study any topic broken into modules, take quizzes, track your progress — all from a simple chat.

---

## Quick Start in 5 Steps

**Step 1** — Install [Claude Desktop](https://claude.ai/download)

**Step 2** — Install [Node.js](https://nodejs.org) (LTS version)

**Step 3** — Clone this repo
```bash
git clone https://github.com/DevanshSrivastava88/Learnix.git
```

**Step 4** — Open Claude Desktop → **Settings → Developer → Edit Config**

This opens the config file in your text editor. Paste this in:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/absolute/path/to/Learnix"
      ]
    }
  }
}
```

> Replace `/absolute/path/to/Learnix` with the actual folder path.
> On Windows use double backslashes: `C:\\Users\\YourName\\Documents\\Learnix`

**Step 5** — Restart Claude Desktop, then say:
> **"Read the CLAUDE.md file in my Learnix folder"**

You're in.

---

## How It Works

- You pick a topic (e.g. Gen AI, Python, System Design)
- Claude breaks it into modules and teaches them one by one
- A 5-question quiz at the end of each module (pass mark: 3/5)
- Progress is saved in `status.json` — pick up exactly where you left off anytime

---

## Setup

### 1. Install Node.js

The filesystem MCP server requires Node.js.
Download from: https://nodejs.org (LTS version)

Verify install:
```bash
node -v
npm -v
```

---

### 2. Configure Claude Desktop

Claude Desktop needs the **filesystem MCP server** so it can read and write files in this folder.

Open Claude Desktop → **Settings → Developer → Edit Config**

This opens the config file directly in your text editor. Add this:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/absolute/path/to/Learnix"
      ]
    }
  }
}
```

Replace `/absolute/path/to/Learnix` with the actual path to this folder.

**Examples:**
- Windows: `C:\\Users\\YourName\\Documents\\Learnix`
- macOS: `/Users/yourname/Documents/Learnix`

> Note: On Windows, use double backslashes `\\` in the path.

---

### 3. Restart Claude Desktop

Fully quit and reopen Claude Desktop after saving the config.

You should see a hammer icon (🔨) in the chat input — that means MCP is active.

---

## Start Learning

Once Claude Desktop is running with MCP enabled, just say:

> **"Read the CLAUDE.md file in my Learnix folder"**

Claude will:
- Check your progress in `status.json`
- Start fresh if nothing exists (asks you what to learn)
- Resume from where you left off if progress exists

That's it.

---

## Folder Structure

```
Learnix/
├── README.md          ← you are here
├── CLAUDE.md          ← instructions Claude follows
├── status.json        ← your progress tracker
└── <topic>/
    ├── 01_<module>.md
    ├── 02_<module>.md
    └── summary.md     ← generated when topic is complete
```

---

## Tips

- You can have multiple topics — Claude handles all of them from one `status.json`
- If you want to restart a topic, set all its module statuses back to `not_started` in `status.json`
- The `summary.md` generated at the end of each topic is a great revision cheat sheet
