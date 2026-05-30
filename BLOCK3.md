# BLOCK3.md — Translation Agent (Master Prompt for Claude Code)

> **Before you start, read in this order:** `CLAUDE.md` → `ARCHITECTURE.md` →
> `SYBILION_DOC.md` → `FLOW_AND_AGENTS.md` → this file. Then begin.
>
> **Source of truth:** `FLOW_AND_AGENTS.md` is canonical (your contract is in
> §4.1). This block file is authoritative for your work. Ignore older docs that
> use a "wine store" — the show case is an **ice cream shop in Vienna**.
>
> **Product:** MarketPilot — *Navigate uncertainty before you launch.*
> **Stack:** Python (FastAPI). LLM hosted on **Featherless**.

---

## 0. Who you are

You are Claude, acting as a **senior backend / LLM engineer with 20 years of
experience.** You write clean prompt-driven services, enforce strict JSON output
from models, handle malformed responses defensively, and apply best practices by
default. You don't over-engineer a hackathon prototype.

---

## 1. Your role

You build the **Translation agent** — the LLM input layer with two operations:

1. **Idea → descriptions:** turn the user's free-text idea into standardized,
   rephrased **descriptions** of the quantifiable factors that affect the
   business.
2. **Corrected descriptions → keywords:** from the user-edited descriptions,
   extract **3–6 keywords**, then call the Data-Engineer agent with them.

The LLM is hosted on **Featherless** — send your requests there (API key from
env, see §5). The LLM here only **structures language** (descriptions, keywords);
it does **not** compute results or make the final decision.

File: `backend/translation_agent.py`. Work directly in `main` at the real path.

---

## 2. Operation A — Idea → descriptions

**Input:**
```json
{ "userInput": "I want to open an ice cream shop in Vienna's 1st district." }
```

**What to do:** send a Featherless LLM request that extracts descriptions of
**quantifiable factors** that could affect the success of the business. You must
inject these **standardized factors** and have the model **rephrase each to fit
the userInput**:

- rent
- staff costs
- location foot traffic
- average basket price
- margin
- seasonality
- tourism dependency

Rephrasing example: instead of bare "rent," produce *"Average rent for a small
retail location in Vienna's 1st district."* Each factor becomes a concrete,
searchable description tailored to the business and location in `userInput`.

**Output (strict JSON, nothing else):**
```json
{ "descriptions": [
  "Average rent for a small retail location in Vienna's 1st district",
  "Typical staff costs for a small food retail business in Vienna",
  "Monthly foot traffic in Vienna's 1st district",
  "Average basket price for ice cream purchases",
  "Gross margin for frozen dessert retail",
  "Seasonal demand pattern for ice cream in Austria",
  "Tourism dependency of central Vienna retail"
] }
```

---

## 3. Operation B — Corrected descriptions → keywords → Data-Engineer

**Input** (the user-corrected list back from the frontend — lines added/removed/
edited):
```json
{ "descriptions": ["Average rent for a small retail location…", "…"] }
```

**What to do:**
1. Extract **3–6 keywords** from the descriptions. The keywords must be (or
   plausibly be) **influential for the statistic** each description will be used
   to analyze — good keywords drive forecast quality (this is real work, not a
   formality).
2. Call the **Data-Engineer agent** (`POST /data/timeseries`, see `BLOCK2.md`)
   with:
   ```json
   { "description": "Average Revenue of Icecreamshops in Vienna with filter",
     "keyWord": ["icecream", "weather"] }
   ```
   Use a representative `description` (you may synthesize a concise statistic
   title from the descriptions) and the extracted keywords as `keyWord`.
3. Return the Data-Engineer's response upward (or hand it to the orchestrator /
   Block 4, per the integration wiring).

> Field name detail: the Data-Engineer expects `keyWord` (camelCase). Match it.

---

## 4. How this maps to the HTTP routes

In the assembled app (`backend/main.py`), your two operations sit behind:
- `POST /api/extract` → Operation A → returns `{ descriptions: [...] }`.
- `POST /api/confirm` → Operation B (extract keywords) → triggers the
  Data-Engineer call and the downstream pipeline → returns `{ job_id }`.

Expose each operation as a clean importable function as well
(`extract_descriptions(user_input)`, `descriptions_to_keywords(descriptions)`),
so the orchestrator can call them directly and so they're unit-testable.

---

## 5. Requirements & best practices

- **Featherless LLM** calls: API key from `FEATHERLESS_API_KEY` (env, never
  hard-coded). Keep the client modular.
- **Strict JSON:** prompt the model to return **only** JSON, no markdown, no
  prose. Parse defensively; on malformed JSON, **retry once** with a stricter
  prompt; if still broken, return a safe fallback (e.g. the standardized factors
  rephrased with a generic location) and mark it.
- **Mock fallback:** if no API key is set, return sensible mock descriptions /
  keywords so the rest of the team is never blocked.
- **Don't decide or calculate.** No revenue, no verdict — that's Block 4. You
  only produce descriptions and keywords.
- **Basic tests** in `tests/` : Operation A returns a `descriptions` list that
  includes all standardized factors rephrased; Operation B returns 3–6 keywords
  and calls the data-engineer with the right shape (mock the call).

## 6. Definition of done

- `POST /api/extract` returns `{ descriptions: [...] }` with the 7 standardized
  factors rephrased to the user's business.
- `POST /api/confirm` extracts 3–6 keywords from the corrected descriptions and
  calls the Data-Engineer with `{ description, keyWord }`.
- Featherless client works with env key; strict-JSON parsing with one retry and a
  mock fallback.
- Clean importable functions, 2–3 tests passing, code at
  `backend/translation_agent.py`.
- If anything conflicts with another doc, follow `FLOW_AND_AGENTS.md`.
