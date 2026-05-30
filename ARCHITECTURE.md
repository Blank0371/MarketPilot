# ARCHITECTURE.md — MarketPilot System Architecture

> **Read order:** `CLAUDE.md` → this file → `backend/MODEL.md` (decision model) →
> `SYBILION_DOC.md`.
>
> The per-block `BLOCK*.md` files have been **removed**. Block-level detail now
> lives in each module's docstring and in `backend/TASK_report_agent_v2.md` (the
> brief to migrate Block 4 to the v2.0 model).
>
> **`backend/MODEL.md` is the canonical source of truth for the decision model.**
> This file is the canonical source of truth for the **system wiring** (services,
> the entry point, the HTTP flow, and the report contract). If anything here
> disagrees with `MODEL.md` about *how the verdict is computed*, `MODEL.md` wins.

**Product:** MarketPilot — *Navigate uncertainty before you launch.*
**Show case:** ice cream shop in Vienna (the system is generic for any offline retail).
**Stack:** Python backend (FastAPI) · TypeScript + React frontend (TanStack Start).
**Target:** working prototype, small team building in parallel.

> ### ⚠️ How to read this document — Current vs Target
>
> This repo is **mid-migration** toward the v2.0 course (a smart LLM wrapper where
> deterministic Python computes every number and the verdict). The doc therefore
> describes **two views**, and tags each section:
>
> - **[Current]** — what actually runs today (what `start.sh` launches and what the
>   frontend calls). This is the live demo path.
> - **[Target v2.0]** — where the architecture is converging. The contracts here are
>   real and referenced by `backend/MODEL.md` and `backend/TASK_report_agent_v2.md`,
>   but the code does **not** yet implement them end-to-end.
>
> §0 summarizes the gap. When Current and Target differ, build new work toward
> Target — but do not assume Target endpoints exist until §0 / §4.1 say they do.

---

## 0. Two views — what runs today vs the v2.0 target

| Dimension | **[Current]** (built, on the demo path) | **[Target v2.0]** (converging toward) |
|---|---|---|
| Entry point | `translation_agent.py` on **:8003** acts as the orchestrator | A dedicated orchestrator `backend/main.py` |
| Public flow | `POST /api/extract` → `POST /api/confirm` (multi-round, stateful sessions) | One synchronous `POST /api/analyze` → full report |
| Who decides the verdict | An **LLM judgment** inside the translation agent (`verdict` ∈ go/no-go/adapt, `score` 1–10) | **Deterministic Python** in `report_agent.py` per `MODEL.md` (LLM only classifies + explains) |
| Forecast (Sybilion) | The translation agent's **own** internal `SybilionClient` (+ mock fallback) | `backend/sybilion_client.py` called by `report_agent.py` |
| Data engineer | `backend/data_engineer.py` on **:8002**, called **in-process** by the translation agent (`get_timeseries`); ice-cream-specific mock generator | Same module, generalized by an LLM profiler + deterministic generator |
| Report shape returned | The translation agent's `{ judgment, forecast_summary }`, adapted on the frontend | The §5.6 report contract, produced directly |
| What-if / recompute | Frontend-local mock recompute (no backend, no Sybilion) | `POST /report/recompute` reusing the cached forecast |
| Decision model `MODEL.md` | **Not wired into the demo path.** `report_agent.py` exists but is on the *old* model and is **not launched** by `start.sh` | `report_agent.py` rewritten per `MODEL.md` (profiler → params → indices → economics → multi-dim verdict → reason) |

**The central gap:** today the verdict and headline numbers come from an **LLM
judgment** in the translation agent. The v2.0 goal is to move that to the
**deterministic `MODEL.md` model** in `report_agent.py` and expose it behind a
single `/api/analyze`. There are currently **two independent Sybilion
integrations** (one inside `translation_agent.py`, one in `sybilion_client.py`);
they should converge onto `sybilion_client.py`.

---

## 1. Concept

A user types a free-text business idea. The pipeline (in its **target** shape):

1. an LLM extracts standardized, rephrased **descriptions** of the quantifiable factors;
2. an LLM extracts **keywords** + a statistic title from those descriptions;
3. a **Data-Engineer** returns a historical monthly **time series** (currently an ice-cream mock; generalized later — see §2);
4. the **Sybilion API** produces a probabilistic forecast over a **requested horizon** (default 6 months);
5. the **report agent** runs the deterministic decision model (`MODEL.md`) — profiler → parameterization → indices → economics → multi-dimensional decision → an LLM phrases the reason — and returns the report JSON;
6. the frontend renders it as a dashboard.

In the **current** build, steps 1–5 are collapsed into the translation agent: it
extracts descriptions, calls the data engineer in-process, runs its own Sybilion
forecast, and produces an **LLM judgment** instead of the deterministic report.
Step 6 is the same dashboard, fed through a frontend adapter (§5.7).

The v2.0 principle: the numeric logic (revenue, costs, investment, the verdict) is
**deterministic Python that actually executes**; the LLM structures input
(descriptions/keywords), classifies the business onto axes, and explains the
finished numbers — it never invents the numbers or the verdict. See `MODEL.md` §0
(principles P1–P6). The migration in §0 is exactly the work of honoring this.

---

## 2. Components & composition

The project is a monorepo of a Python backend, a React frontend, and two
standalone agent sub-projects. **Wired** = on the live demo path; **Roadmap** =
present in the repo but not launched/integrated yet.

### 2.1 Backend modules (`backend/`)

| Module | Block | Status | Responsibility |
|--------|-------|--------|----------------|
| `translation_agent.py` | 3 (+ de-facto orchestrator) | **Wired** (:8003) | Idea → descriptions → keywords + title; runs the whole pipeline over stateful, multi-round sessions; owns its **own** `FeatherlessClient` (LLM) and `SybilionClient` (+ mock); calls `data_engineer.get_timeseries` in-process; returns an LLM **judgment** + forecast summary. |
| `data_engineer.py` | 2 | **Wired** (:8002) | Historical monthly time-series endpoint + `get_timeseries(...)`. Currently an **ice-cream-specific** deterministic mock generator; `select_source` is a stub registry for future real sources. |
| `report_agent.py` | 4 | **Roadmap** (not launched) | The decision-model report producer (`/report/build`, `/report/recompute`). **Still on the OLD model** (`Assumptions`, the `BASKETS_PER_INDEX_POINT` scale, Monte-Carlo break-even, `confidence_from_backtest`, a legacy subprocess-codegen path). `backend/TASK_report_agent_v2.md` is the brief to rewrite it per `MODEL.md`. |
| `sybilion_client.py` | 4 | **Roadmap** (used only by `report_agent.py`) | Sybilion HTTP/SDK wrapper: `build_forecast_request`, `get_forecast(...)` with `source ∈ live\|cache\|mock`, artifact parsing, `--seed` cache writer. Reads quantiles from `quantile_forecast` keys `"0.1"/"0.5"/"0.9"`. |

> Not present (despite older docs / READMEs referencing them): `backend/main.py`,
> `backend/contracts.py`, `backend/intent_extractor.py`. These are **Target**
> artifacts — the orchestrator and shared Pydantic models do not exist yet. Each
> module currently defines its own `app`, models, and (where needed) clients.

### 2.2 Frontend (`frontend/`) — Block 1, **Wired** (:5173)

React + TypeScript on **TanStack Start** (file-based routing: `routeTree.gen.ts`,
`router.tsx`, `routes/`, `server.ts`, `start.ts`), Vite, Tailwind + shadcn/ui
components. Package manager is **bun** (`bun.lock`, `bunfig.toml`); `start.sh`
launches it with `npm run dev`.

- Talks to the **translation agent** at `http://127.0.0.1:8003` (`src/lib/api.ts`,
  `BACKEND_BASE`): `POST /api/extract`, `POST /api/confirm`.
- Adapts the confirm `judgment` into its internal `Report` shape via
  `adaptConfirmResponseToReport` (§5.7).
- `src/lib/mockApi.ts` + `mockData.ts` provide an offline mode (`DataMode =
  "mock" | "endpoint"`) so the dashboard works without a backend.
- **Legacy leftovers** from the old async design still exist but are unused by the
  current synchronous path: `ConfirmResponse { job_id }`, `JobStatus`,
  `PipelineStep` (in `types.ts`) and `components/PollingLoader.tsx`.
- The dashboard section order and the six founder-controllable what-if overrides
  are specified in `frontend/CLAUDE.md`. **What-if is frontend-local/mock — it
  never calls Sybilion.**

### 2.3 Standalone agent sub-projects — **Roadmap**

- **`data-engineer-agent/`** — a full standalone FastAPI service ("Data Engineer
  Agent" v0.1.0; routes `/dry-run`, `/query`, `/sources`, `/datasets`) with
  Eurostat/commodities adapters, a YAML dataset/source registry, a sandboxed code
  runner (Jinja templates + Docker), and `intent_extractor` / `source_planner` /
  `code_planner` agents. Its own `pyproject.toml` and tests. This is the **real**
  data engineer that `backend/data_engineer.py` mocks. **Not on the demo path.**
  If wired in later, a relevance filter must reject non-demand metrics (e.g.
  inflation) before they reach the report model.
- **`translation-agent/`** — an empty placeholder (only `.gitignore`); superseded
  by `backend/translation_agent.py`.

---

## 3. Architecture diagrams

### 3.1 [Current] — what runs today

```
User Input (Front-End, TanStack Start / React, :5173)
        │
        │  POST /api/extract   { userInput }
        ▼
┌────────────────────────────────────────────────────────────────┐
│  TRANSLATION AGENT  (backend/translation_agent.py, :8003)        │
│  de-facto orchestrator — stateful multi-round sessions           │
│                                                                  │
│   extract_descriptions(userInput)        [LLM, Featherless]      │
│        → { descriptions }                                        │
└────────────────────────────────────────────────────────────────┘
        │  user edits/confirms descriptions on the frontend
        │  POST /api/confirm   { descriptions }   (or /api/refine for next round)
        ▼
┌────────────────────────────────────────────────────────────────┐
│  TRANSLATION AGENT  (:8003)  — pipeline per round                │
│                                                                  │
│   keywords + statistic_title(descriptions)   [LLM]               │
│   get_timeseries(description, keywords)       ── in-process ──▶   │
│        ↳ backend/data_engineer.py  (:8002 standalone too)        │
│        → { timeseries_metadata, timeseries }                     │
│   SybilionClient.run_forecast(payload)        [own client +mock] │
│        → forecast, signals                                       │
│   LLM judgment over the data        [LLM, NOT MODEL.md]          │
│        → { verdict go|no-go|adapt, score 1–10, ... }             │
└────────────────────────────────────────────────────────────────┘
        │  { session_id, round, judgment, forecast_summary }   (§5.2)
        ▼
[Front-End]  adaptConfirmResponseToReport(...)  →  internal Report (§5.7)
   dashboard: verdict · financials · forecast · drivers · investment · reasoning
        │
        │  what-if controls  →  frontend-local mock recompute (no backend, no Sybilion)
        ▼
   Before/After comparison updates locally

  ─ ─ ─ not wired ─ ─ ─
  report_agent.py (:standalone)  /report/build · /report/recompute   [OLD model]
  sybilion_client.py             get_forecast (live|cache|mock)
  data-engineer-agent/           /query · /sources · /datasets        [real sources]
```

### 3.2 [Target v2.0] — where it converges

```
User Input (Front-End)
        │
        │  POST /api/analyze   { userInput, forecast_horizon_months? }
        ▼
┌───────────────────────────────────────────────────────────┐
│  ORCHESTRATOR  (backend/main.py)  — one synchronous call    │
│                                                             │
│   extract_descriptions(userInput)        [Block 3, LLM]     │
│   keywords_and_title(descriptions)       [Block 3, LLM]     │
│   get_timeseries(title, keywords)        [Block 2]          │
│   build_report(timeseries, meta, ...)    [Block 4]          │
│        ├─ sybilion_client.get_forecast() → forecast bundle  │
│        └─ decision model (MODEL.md):                        │
│             profiler(LLM) → params → indices → economics    │
│             → multi-dim decision → reason(LLM)              │
│        → report JSON (§5.6)                                 │
└───────────────────────────────────────────────────────────┘
        │  full report (§5.6) in one response
        ▼
[Front-End — Results Dashboard]
        │  POST /report/recompute  { ...inputs, overrides }
        ▼
re-derives economics + verdict on the cached forecast (no Sybilion call)
```

---

## 4. HTTP routes

### 4.1 [Current] — live services

`start.sh` launches **three** processes: the data engineer, the translation agent,
and the frontend.

| Service (port) | Method | Route | Purpose |
|---|---|---|---|
| Translation agent (**:8003**) | `POST` | `/api/extract` | `{ userInput }` → `{ descriptions }` (422 `business_rejected` if the idea is rejected). |
| Translation agent (:8003) | `POST` | `/api/confirm` | `{ descriptions }` → `{ session_id, round, conversation_turns, judgment, forecast_summary }` (§5.2). Synchronous; starts a session. |
| Translation agent (:8003) | `POST` | `/api/refine` | `{ sessionId?, descriptions, initialDescriptions? }` → same shape, next round (multi-turn what-if at the idea level). |
| Translation agent (:8003) | `GET` | `/api/session/{id}` | session snapshot (rounds, merged descriptions/keywords, observation count). |
| Translation agent (:8003) | `GET` | `/health` | health + `llm_available` / `sybilion_available`. |
| Data engineer (**:8002**) | `POST` | `/data/timeseries` | `{ description, keyWord[] }` → `{ timeseries_metadata, timeseries }` (§5.4). Also imported **in-process** by the translation agent. |
| Data engineer (:8002) | `GET` | `/health` | health check. |
| Report agent (**not launched**) | `POST` | `/report/build` | `{ timeseries, timeseries_metadata, userInput, descriptions }` → report (OLD model). |
| Report agent (not launched) | `POST` | `/report/recompute` | `{ ..., overrides }` → recompute on the cached forecast. Exists, but unused by the demo. |

CORS on the translation agent allows `:5173`, `:8080`, `:3000` (localhost + 127.0.0.1).

### 4.2 [Target v2.0] — the synchronous spine

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/analyze` | `{ userInput, forecast_horizon_months? }` → full report JSON (§5.6). Runs the whole pipeline synchronously. |
| `POST` | `/report/recompute` | `{ ...inputs, overrides }` → updated report JSON, reusing the cached forecast (no Sybilion call). Powers the live what-if. |
| `GET`  | `/api/health` | health check. |

**Notes:**
- `forecast_horizon_months` is the **forecast horizon contract** (`MODEL.md` §2.2): default 6, range 1–12, passed straight to Sybilion as `soft_horizon`. In the current build the horizon surfaces as `forecast_summary.forecast_horizon` (the translation agent's `soft_horizon`).
- The old async pair `/api/status/{job_id}` + `/api/result/{job_id}` is **removed**. See §9.

---

## 5. JSON contracts

Match field names exactly.

### 5.1 [Current] `POST /api/extract`  (Block 3a)
Input: `{ "userInput": "I want to open an ice cream shop in Vienna's 1st district." }`
Output:
```json
{ "descriptions": [
  "Average rent for a small retail location in Vienna's 1st district",
  "Monthly tourism footfall in central Vienna",
  "Seasonal demand pattern for frozen desserts in Austria"
] }
```

### 5.2 [Current] `POST /api/confirm` (and `/api/refine`)
The current decision payload. The `judgment` is an **LLM** verdict, not the
deterministic `MODEL.md` report.
```json
{
  "session_id": "…",
  "round": 1,
  "conversation_turns": 1,
  "judgment": {
    "verdict": "adapt",                       // go | no-go | adapt
    "score": 5,                                // integer 1–10
    "summary": "…",
    "estimated_monthly_revenue_eur": 18500,
    "estimated_monthly_costs_eur": 13200,
    "estimated_monthly_profit_eur": 5300,
    "payback_months": 24,
    "strengths": ["…"],
    "risks": ["…"],
    "recommendation": "…",
    "changed_from_previous": null              // what changed vs the last round, or null
  },
  "forecast_summary": {
    "statistic_title": "Average revenue of ice cream shops in Vienna",
    "keywords": ["icecream", "vienna", "seasonality"],
    "observations": 60,
    "forecast_horizon": 6,                     // Sybilion soft_horizon
    "forecast_series": { "2026-06-01": 1040.0, "…": 0.0 },
    "top_drivers": []
  }
}
```

### 5.3 [Current] keywords + title (internal to the translation agent)
Produced inside the pipeline (LLM), not a separate HTTP route:
```json
{ "keywords": ["icecream", "vienna", "seasonality", "tourism"],
  "statistic_title": "Average revenue of ice cream shops in Vienna" }
```

### 5.4 [Current] Data-Engineer contract (`data_engineer.py`)
Request (note the camelCase `keyWord`):
```json
{ "description": "Average revenue of ice cream shops in Vienna",
  "keyWord": ["icecream", "weather"] }
```
Response:
```json
{
  "timeseries_metadata": {
    "title": "Average revenue of ice cream shops in Vienna",
    "description": "Average revenue of ice cream shops in Vienna.",
    "keywords": ["icecream", "restaurants", "weather", "seasons"]
  },
  "timeseries": {
    "2021-12-01": 218.5, "2022-01-01": 148.1, "2022-02-01": 145.9,
    "2022-03-01": 162.4, "2022-04-01": 168.7, "2022-05-01": 166.2
  }
}
```
The output is always `{ "YYYY-MM-DD": float }` (≥60 monthly points). Today the
series is an ice-cream-specific deterministic mock; the **target** keeps this exact
contract while an LLM profiler + generic generator shape the series, so it never
breaks downstream.

### 5.5 [Both] Sybilion request
Built from §5.4 (by the translation agent today; by `sybilion_client.py` in the target):
```json
{
  "pipeline_version": "v1",
  "frequency": "monthly",
  "soft_horizon": 6,
  "recency_factor": 0.5,
  "backtest": true,
  "timeseries_metadata": { "title": "…", "description": "…", "keywords": ["…"] },
  "timeseries": { "2021-12-01": 218.5, "…": "…" }
}
```
`soft_horizon` is set from the requested horizon. Forecast quantiles are read from
`quantile_forecast` keys `"0.1"` / `"0.5"` / `"0.9"` (never `p10/p50`).

### 5.6 [Target v2.0] Final report contract (`/api/analyze` → Front-End)
This is the canonical report the v2.0 `report_agent.py` must produce and the shape
the frontend ultimately renders. Referenced by `backend/MODEL.md` and
`backend/TASK_report_agent_v2.md`. **Not produced end-to-end yet** — the current
demo path uses §5.2 + the frontend adapter (§5.7) instead.
```json
{
  "decision": {
    "label": "Adapt concept",
    "score": 72,
    "risk_level": "Medium",
    "confidence": 0.68,
    "summary": "Strong summer demand, but winter seasonality creates downside risk."
  },
  "expected_revenue": {
    "expected_monthly_revenue_eur": 18500,
    "expected_monthly_costs_eur": 13200,
    "expected_monthly_profit_eur": 5300,
    "downside_monthly_profit_eur": -2100,
    "upside_monthly_profit_eur": 11200,
    "break_even_probability": 0.67,
    "payback_months": 18
  },
  "investment_cost": {
    "estimated_initial_investment_eur": 120000,
    "breakdown": [
      { "category": "Initial inventory", "amount": 30000 },
      { "category": "Store setup", "amount": 45000 },
      { "category": "Launch marketing", "amount": 15000 },
      { "category": "Legal and licensing", "amount": 10000 },
      { "category": "Cash buffer", "amount": 20000 }
    ]
  },
  "graphs": {
    "demand_forecast": [
      { "date": "2026-06-01", "historical": null, "forecast": 1040, "low": 820, "high": 1280 }
    ],
    "historical_series": [
      { "date": "2025-06-01", "historical": 980, "forecast": null, "low": null, "high": null }
    ]
  },
  "drivers": [
    { "name": "Vienna tourism", "importance": 0.82, "direction": "positive", "horizon": 1 },
    { "name": "Seasonality", "importance": 0.74, "direction": "negative", "horizon": 6 }
  ],
  "backtest": { "mape": 0.118, "rmse": 94.2, "quality": "medium-high" },
  "reason": {
    "main_reason": "Strong summer demand, but winter seasonality creates downside risk.",
    "positive_factors": ["Summer tourism lifts peak-season demand.", "High product margin."],
    "negative_factors": ["Winter demand falls sharply.", "Rent runs year-round."],
    "recommended_actions": ["Add a winter product line.", "Negotiate seasonal rent."]
  },
  "runtime": {
    "mode": "prod",
    "fallbacks": []
  }
}
```

> **Notes:**
> - `decision.label` ∈ **Launch · Adapt concept · Delay · Do not launch** — drive verdict color from this. The label is **multi-dimensional** (`MODEL.md` §8.3): it depends on break-even AND payback (relative to the business profile) AND confidence AND risk — not on break-even alone.
> - `decision.confidence` is the composite confidence index `CONF` (`MODEL.md` §6.5): a blend of forecast accuracy (MAPE), history sufficiency, and band tightness. It is **not** a single MAPE transform.
> - `graphs.*` points carry `historical`, `forecast`, `low`, `high` so the chart shows history, the forecast continuation, and the confidence band.
> - `backtest` is surfaced on the dashboard and feeds `decision.confidence`. The jury rewards backtest discipline.
> - `drivers[].horizon` lets the UI show how importance shifts across the forecast horizon (month 1 vs month 6).
> - **`runtime`** (`MODEL.md` §1.1): `mode` is `dev` or `prod`; `fallbacks` lists any fallback that fired (e.g. `"sybilion_unavailable->synthetic_forecast"`). An empty list means everything was computed on real paths.

### 5.7 [Current] Frontend internal `Report` + adapter
The frontend keeps its own `Report` type (`src/lib/types.ts`) that **predates** the
§5.6 names. `adaptConfirmResponseToReport` (`src/lib/api.ts`) maps the §5.2
`judgment` into it, filling unprovided fields (graphs, drivers, investment,
backtest) from mock data. Key differences from §5.6:

| §5.6 (target) | Frontend `Report` (current) |
|---|---|
| `expected_revenue { expected_monthly_* }` | `financials { expected_monthly_revenue, …_costs, …_profit, estimated_initial_investment, break_even_probability, payback_period_months }` |
| `investment_cost { breakdown[] }` | `investment_breakdown[]` |
| `graphs.*` points `{ date, historical, forecast, low, high }` | `historical_series[{ month, value }]`, `demand_forecast[{ month, low, mid, high }]` |
| `backtest { mape, rmse, quality }` | `backtest { mape, quality }` |
| `runtime { mode, fallbacks }` | (absent) |

Converging the backend onto §5.6 and the frontend onto that same shape (dropping
the adapter and the legacy polling types) is part of the §0 migration.

---

## 6. File structure (actual)

```
ZeroOneHack_01/
├── backend/
│   ├── translation_agent.py    ← Block 3 + de-facto orchestrator; entry point (:8003)
│   ├── data_engineer.py        ← Block 2: time-series endpoint + get_timeseries (:8002); ice-cream mock
│   ├── report_agent.py         ← Block 4: report producer (OLD model; not launched)
│   ├── sybilion_client.py      ← Block 4: Sybilion wrapper + synthetic fallback (used only by report_agent)
│   ├── MODEL.md                ← decision-model specification (canonical for the verdict)
│   ├── TASK_report_agent_v2.md ← brief: migrate report_agent.py to the v2.0 MODEL.md model
│   ├── backend_README.md       ← backend run/dev guide
│   ├── requirements.txt
│   └── __init__.py             ← auto-loads repo-root .env
├── frontend/                   ← Block 1: TanStack Start + React + TS (:5173)
│   ├── src/
│   │   ├── routes/ · router.tsx · routeTree.gen.ts · server.ts · start.ts
│   │   ├── components/         ← dashboard + ui/ (shadcn)
│   │   └── lib/                ← api.ts (calls :8003), types.ts, mockApi.ts, mockData.ts
│   ├── CLAUDE.md               ← frontend design + demo-flow spec
│   └── package.json · bun.lock · bunfig.toml
├── data-engineer-agent/        ← Roadmap: standalone real data engineer (Eurostat, registry, sandbox)
│   └── app/ · tests/ · pyproject.toml
├── translation-agent/          ← empty placeholder (superseded by backend/translation_agent.py)
├── tests/
│   ├── test_translation_agent.py
│   ├── test_data_engineer.py
│   ├── test_sybilion_client.py
│   └── test_report_agent.py
├── mock/
│   ├── timeseries_icecream.json   ← Data-Engineer mock
│   ├── forecast.json              ← cached Sybilion forecast (fallback)
│   ├── external_signals.json      ← cached drivers (fallback)
│   └── backtest_metrics.json      ← cached backtest (fallback)
├── start.sh                    ← launches data_engineer (:8002) + translation_agent (:8003) + frontend (:5173)
├── ARCHITECTURE.md             ← this file (canonical for system wiring)
├── CLAUDE.md                   ← project entry point / behavior
├── SYBILION_DOC.md · FLOW_AND_AGENTS.md · FOR_DEVELOPERS.md · Track_3_description.md
└── README.md
```

> No `backend/main.py`, `backend/contracts.py`, or `backend/intent_extractor.py`
> yet — see §2.1. `mock/sample_report.json` (a frozen §5.6 stub) is also a Target
> artifact; the frontend currently uses `src/lib/mockData.ts` for offline data.

---

## 7. Run modes (dev / prod)

The decision model honors `MODEL_MODE=dev|prod` (`MODEL.md` §1.1 / P6):

- **`dev`** — no fallbacks. If the LLM does not answer, Sybilion is unavailable, or any step fails → an **error is raised**. Used during development so silent stubs do not mask bugs.
- **`prod`** — fallbacks enabled but **loud**: a synthetic Sybilion forecast, a neutral profiler profile, a deterministic reason template. Every fallback is recorded in the report's `runtime.fallbacks` and surfaced to the user/jury.

Default for the live demo: **`prod`** (must never crash on stage).

> **[Current]** `runtime.fallbacks` and `MODEL_MODE` are fully realized only in the
> v2.0 `report_agent.py` (Target). The live translation agent has its own resilience
> (a `_mock_sybilion_forecast` fallback and a deterministic neutral judgment when the
> LLM is unavailable) but does **not** yet emit a `runtime` block.

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sybilion forecast slow / unavailable | Medium | High | The translation agent falls back to `_mock_sybilion_forecast`; the Target `sybilion_client` caches a real forecast to `mock/` and flags a synthetic fallback in `runtime.fallbacks` |
| No real time series found | Medium | Medium | `data_engineer.py` returns a documented mock series; the `data-engineer-agent/` roadmap project adds real sources later |
| LLM returns malformed JSON | Medium | Medium | Strict-JSON prompting + one retry; the translation agent falls back to a neutral judgment; the Target report falls back to a neutral profile / reason template (`dev` errors instead) |
| Contract drift between blocks | Medium | High | Contracts fixed here and in `MODEL.md`; each module exposes one clean interface; the frontend `mockData.ts` decouples the dashboard |
| Verdict comes from the LLM, not deterministic Python | **High (current)** | High | This is the §0 migration: move the verdict to the `MODEL.md` model in `report_agent.py`; until then the demo is honest that the judgment is LLM-produced |
| Two divergent Sybilion integrations | Medium | Medium | Converge `translation_agent`'s internal client onto `backend/sybilion_client.py` |
| API keys missing | Low | High | Featherless + Sybilion keys checked at startup (`/health` reports availability); `prod` mock fallback, `dev` clear error |

---

## 9. Migration note — three layers

The architecture has moved through three stages; the repo currently straddles the
last two:

| Stage | State |
|---|---|
| **Original (superseded)** | Async flow: `/api/confirm` → `{job_id}` → poll `/api/status` → `/api/result`; "LLM writes & executes its own Python"; fixed 6-month horizon; one-dimensional verdict. Leftovers: the frontend's `JobStatus`/`PipelineStep`/`PollingLoader`. |
| **Current (built)** | Synchronous, but split across two services: `translation_agent` (:8003) extract → confirm/refine over stateful sessions, with an **LLM judgment**; `data_engineer` (:8002). `report_agent`+`sybilion_client` exist on the **old deterministic model** but are **not wired in**. |
| **Target v2.0 (converging)** | One synchronous `POST /api/analyze` via `backend/main.py`; the **deterministic `MODEL.md` model** in `report_agent.py` produces the §5.6 report (LLM only classifies + explains); `forecast_horizon_months` contract; multi-dimensional verdict; `runtime` block; `/report/recompute` for what-if. |

Key deltas from Original → Target (for anyone reading older `BLOCK*.md` /
`FLOW_AND_AGENTS.md` notes — **the v2.0 docs win**, flag mismatches rather than
reconciling silently):

| Old design (superseded) | v2.0 (target) |
|---|---|
| Async poll: `/api/confirm` → `{job_id}` → `/api/status` → `/api/result` | **Synchronous** `POST /api/analyze` → full report in one call |
| "LLM writes & executes its own Python" to compute economics | Deterministic Python computes; the LLM **classifies** (profiler) and **explains** (reason) (`MODEL.md` §11) |
| Single magic `BASKETS_PER_INDEX_POINT = 23` | Traceable `scale` cascade with sources (`MODEL.md` §5.7, §7.1) |
| One-dimensional verdict (break-even only) | Multi-dimensional verdict: break-even + payback-vs-profile + confidence + risk (`MODEL.md` §8.3) |
| Hard-coded 6-month horizon | `forecast_horizon_months` request contract (`MODEL.md` §2.2) |
| "Plain LLM wrapper forbidden" hard rule | Supervisor-approved **smart LLM wrapper**; accuracy/traceability is the priority criterion (`MODEL.md` §0). The numbers are deterministic, so the spirit holds |

---

## 10. Environment

```bash
export FEATHERLESS_API_KEY=...     # translation + (target) profiler + report LLM
export SYBILION_API_TOKEN=...      # Sybilion (optional → synthetic fallback in prod)
export MODEL_MODE=prod             # dev | prod  (see §7); default prod for the demo
```

A repo-root `.env` is auto-loaded on import (`backend/__init__.py`); shell variables
take precedence. Copy `.env-example` to `.env` for local dev.

**Ports** (overridable in `start.sh`): data engineer **:8002**, translation agent
**:8003**, frontend **:5173**. The report agent has no assigned port in `start.sh`
(run it standalone with `uvicorn backend.report_agent:app` if needed).

**Run everything:** `./start.sh` (needs a Python venv at `env/` or `.venv/` with
`backend/requirements.txt`, and `frontend/node_modules` installed).
