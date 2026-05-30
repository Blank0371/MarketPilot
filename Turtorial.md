# MarketPilot — Translation Agent: Getting Started

This guide walks you through setting up and running the agent on your computer, step by step. No prior experience needed.

---

## What you need before you start

- **Python 3.10 or newer** — check by opening a terminal and typing `python --version` (Windows) or `python3 --version` (Mac). If you don't have it, download it from [python.org](https://www.python.org/downloads/).
- **Your API keys** — you need a Featherless key and a Sybilion key. Without them the agent still runs, but uses placeholder data instead of real forecasts.
- **The project folder** — wherever you saved `translation_agent.py` and the rest of the code.

---

## Step 1 — Open a terminal in your project folder

**Windows:**
1. Open File Explorer and navigate to your project folder
2. Click the address bar at the top, type `cmd`, and press Enter
3. A black Command Prompt window opens, already inside your folder

**macOS:**
1. Open Finder and navigate to your project folder
2. Right-click the folder → "New Terminal at Folder"
3. A Terminal window opens, already inside your folder

---

## Step 2 — Create a virtual environment

A virtual environment keeps the project's packages separate from the rest of your computer. You only do this once.

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You know it worked when you see `(venv)` at the start of your terminal line, like this:
```
(venv) C:\Users\you\marketpilot>
```

---

## Step 3 — Install the dependencies

Still inside your terminal with `(venv)` active:

```
pip install fastapi uvicorn httpx python-dotenv pydantic
```

Wait for it to finish. This downloads all the packages the agent needs.

---

## Step 4 — Create your `.env` file

The `.env` file stores your API keys and settings. Create a new file called exactly `.env` (note the dot at the start) inside your project folder, and paste this inside it:

```env
FEATHERLESS_API_KEY=your-featherless-key-here
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
FEATHERLESS_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct

SYBILION_API_KEY=your-sybilion-key-here
SYBILION_BASE_URL=https://api.sybilion.dev

DATA_ENGINEER_URL=http://localhost:8002

SESSION_TTL_SECONDS=7200
DARK_MODE=false
```

Replace `your-featherless-key-here` and `your-sybilion-key-here` with your actual keys. If you don't have keys yet, leave them as-is — the agent will use placeholder data and still respond.

> **Windows tip:** Windows sometimes hides file extensions. To make sure your file is called `.env` and not `.env.txt`, open Notepad, paste the content, then go to File → Save As, change "Save as type" to "All Files", and name it `.env`.

---

## Step 5 — Start the server

Make sure `(venv)` is still active in your terminal, then run:

**Windows:**
```cmd
uvicorn backend.translation_agent:app --host 0.0.0.0 --port 8003 --reload
```

**macOS:**
```bash
uvicorn backend.translation_agent:app --host 0.0.0.0 --port 8003 --reload
```

> If your file is not inside a `backend` folder but directly in the project root, use this instead:
> ```
> uvicorn translation_agent:app --host 0.0.0.0 --port 8003 --reload
> ```

You should see something like this — that means it's working:
```
INFO:     Uvicorn running on http://0.0.0.0:8003 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

The server is now running. **Do not close this terminal window** — closing it stops the server.

---

## Step 6 — Verify it's alive

Open a **second** terminal window (keep the first one running), navigate to your project folder again, and run:

**Windows:**
```cmd
curl http://localhost:8003/health
```

**macOS:**
```bash
curl http://localhost:8003/health
```

You should get back something like:
```json
{
  "status": "ok",
  "agent": "translation",
  "version": "4.0.0",
  "active_sessions": 0,
  "llm_available": true,
  "sybilion_available": true,
  "dark_mode": false
}
```

If `llm_available` is `false`, your Featherless key is missing or wrong. The agent still works but uses placeholder descriptions.

---

## Making requests

All the commands below go into your **second** terminal (the one without the server running).

---

### `POST /api/extract` — Turn a business idea into factor descriptions

This is the first step. You give it a plain-text business idea and it returns a list of standardised factor descriptions for the user to review.

**Windows:**
```cmd
curl -X POST http://localhost:8003/api/extract -H "Content-Type: application/json" -d "{\"userInput\": \"I want to open a wine shop in Vienna\"}"
```

**macOS:**
```bash
curl -X POST http://localhost:8003/api/extract \
  -H "Content-Type: application/json" \
  -d '{"userInput": "I want to open a wine shop in Vienna"}'
```

**What you get back:**
```json
{
  "descriptions": [
    "Average rent for a small retail location in Vienna",
    "Typical staff costs for a wine shop in Vienna",
    "Monthly foot traffic in Vienna city center",
    "Average basket price per customer for wine",
    "Typical gross margin for wine retail",
    "Seasonal demand pattern for wine retail across the year",
    "Tourism dependency of wine retail in Vienna",
    "Wine licensing requirements in Austria",
    "Average competitor density for wine retail in Vienna",
    "Customer age distribution for wine buyers in Vienna",
    "Online wine delivery market share in Austria",
    "Average supplier lead time for wine in Austria"
  ]
}
```

The user can now edit this list — delete descriptions they don't want, add their own — before sending it to `/api/confirm`.

---

### `POST /api/confirm` — Run the full analysis pipeline

This takes the confirmed list of descriptions and runs the full pipeline: keywords → Data-Engineer → Sybilion forecast → LLM judgment.

> ⚠️ This request takes **1–4 minutes** to complete because it waits for the Sybilion forecast jobs to finish. The terminal with the server will show progress logs while it works.

**Windows:**
```cmd
curl -X POST http://localhost:8003/api/confirm -H "Content-Type: application/json" -d "{\"descriptions\":[\"rent costs for commercial property in central Vienna\",\"staff costs for wine shop in Vienna\",\"foot traffic in central Vienna shopping district\",\"average basket price for wine in Vienna\",\"margin on wine sales in Vienna\",\"seasonality of wine sales in Vienna\",\"tourism dependency of wine sales in Vienna\",\"wine import and export regulations in Austria\",\"wine certification and quality standards in Austria\",\"wine consumer preferences in Vienna\",\"wine distribution channels in Vienna\",\"wine supplier reliability in Vienna\"]}"
```

**macOS:**
```bash
curl -X POST http://localhost:8003/api/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "descriptions": [
      "rent costs for commercial property in central Vienna",
      "staff costs for wine shop in Vienna",
      "foot traffic in central Vienna shopping district",
      "average basket price for wine in Vienna",
      "margin on wine sales in Vienna",
      "seasonality of wine sales in Vienna",
      "tourism dependency of wine sales in Vienna",
      "wine import and export regulations in Austria",
      "wine certification and quality standards in Austria",
      "wine consumer preferences in Vienna",
      "wine distribution channels in Vienna",
      "wine supplier reliability in Vienna"
    ]
  }'
```

**What you get back:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "round": 1,
  "conversation_turns": 1,
  "judgment": {
    "verdict": "go",
    "score": 7,
    "summary": "The Viennese wine retail market shows stable demand with strong tourism upside. Margins are healthy and seasonality is manageable with the right inventory strategy.",
    "estimated_monthly_revenue_eur": 22000,
    "estimated_monthly_costs_eur": 15400,
    "estimated_monthly_profit_eur": 6600,
    "payback_months": 18,
    "strengths": [
      "High tourism footfall supports premium pricing",
      "Austria's wine culture creates a loyal local customer base"
    ],
    "risks": [
      "High central Vienna rents compress margins",
      "Seasonal dips in January–February require cash reserves"
    ],
    "recommendation": "Launch in Q2 to capture spring tourism; negotiate a 3-year lease to lock in rent.",
    "changed_from_previous": null
  },
  "forecast_summary": {
    "statistic_title": "Average revenue of wine shop in Vienna",
    "keywords": ["wine", "vienna", "retail", "tourism", "seasonality"],
    "observations": 36,
    "forecast_horizon": 6,
    "forecast_series": {
      "2025-04-01": 188.5,
      "2025-05-01": 192.3,
      "2025-06-01": 197.1
    },
    "top_drivers": [
      {"name": "Consumer Price Index", "importance": 0.81, "direction": "positive"},
      {"name": "Tourism Arrivals",     "importance": 0.57, "direction": "positive"}
    ],
    "per_description": [
      {
        "description": "rent costs for commercial property in central Vienna",
        "forecast_series": {"2025-04-01": 24.5, "2025-05-01": 24.8}
      }
    ]
  }
}
```

**Save the `session_id`** — you'll need it if you want to refine the analysis later with `/api/refine`.

---

## Stopping the server

Go back to the first terminal window (where the server is running) and press:

```
CTRL + C
```

The server shuts down cleanly.

---

## Common problems

| Problem | Likely cause | Fix |
|---|---|---|
| `curl: command not found` (Windows) | curl not installed | Use Windows 10/11 — curl is built in. Or download from [curl.se](https://curl.se/windows/) |
| `Connection refused` | Server isn't running | Make sure the first terminal is open and shows "Application startup complete" |
| `ModuleNotFoundError` | Package not installed | Run `pip install fastapi uvicorn httpx python-dotenv pydantic` again |
| `(venv)` disappeared | Virtual env deactivated | Run `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac) again |
| `llm_available: false` in `/health` | Missing Featherless key | Check your `.env` file and make sure there are no spaces around the `=` sign |
| `/api/confirm` returns immediately with placeholder data | Sybilion key missing | Check your `.env` file for `SYBILION_API_KEY` |
| Server shows `Address already in use` | Port 8003 is taken | Change the port: add `--port 8004` to the uvicorn command, and update all your curl requests to use `8004` |

---

## Quick reference

| What | Command |
|---|---|
| Start server | `uvicorn backend.translation_agent:app --host 0.0.0.0 --port 8003 --reload` |
| Check server health | `curl http://localhost:8003/health` |
| Extract descriptions | `curl -X POST http://localhost:8003/api/extract ...` |
| Run full analysis | `curl -X POST http://localhost:8003/api/confirm ...` |
| View session state | `curl http://localhost:8003/api/session/{session_id}` |
| Interactive API docs | Open `http://localhost:8003/docs` in your browser |
| Stop server | Press `CTRL + C` in the server terminal |

> **Tip:** The interactive docs at `http://localhost:8003/docs` let you test every endpoint by clicking and filling in forms — no curl needed.