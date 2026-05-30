# ARCHITECTURE.md — MarketPilot System Architecture

> Read order: `CLAUDE.md` → this file → `SYBILION_DOC.md` → `FLOW_AND_AGENTS.md`
> → your block file.
>
> **`FLOW_AND_AGENTS.md` is the canonical source of truth.** This file expands it
> into the block/file structure, the HTTP routes, and the result contract. If
> anything here disagrees with `FLOW_AND_AGENTS.md`, that file wins.

**Product:** MarketPilot — *Navigate uncertainty before you launch.*
**Show case:** ice cream shop in Vienna (system is generic for any retail).
**Stack:** Python backend · TypeScript + React frontend.
**Target:** working prototype, 4 people building in parallel.

---

## 1. Concept

A user types a free-text business idea. An LLM extracts standardized, rephrased
**descriptions** of the quantifiable factors. The user confirms/edits them. From
the corrected descriptions an LLM extracts **keywords**. A data-engineer returns
a historical monthly **time series**. The Sybilion API produces a probabilistic
**6-month forecast**. A report LLM then writes and executes **its own Python** to
compute expected revenue, graphs, investment cost, and a **decision + reason**,
returned as JSON and rendered on a dashboard.

---

## 2. Block ↔ agent mapping

| Block | Agent (FLOW_AND_AGENTS §4) | Owner builds |
|-------|----------------------------|--------------|
| **Block 1** | Front-End | Idea input · description confirmation · results dashboard |
| **Block 2** | Data-Engineer agent | POST endpoint returning the time-series JSON (mock now, real sources later) |
| **Block 3** | Translation agent | idea → descriptions, then descriptions → keywords (LLM on Featherless) |
| **Block 4** | Sybilion + report agent | Sybilion SDK forecast + LLM-written/executed Python → report JSON |

---

## 3. Architecture diagram

```
User Input (Front-End, React/TS)
        │  POST /api/extract   { userInput }
        ▼
[Block 3 — Translation agent, LLM]
extract standardized descriptions of quantifiable factors
        │  { descriptions: [...] }
        ▼
[Front-End — Confirm descriptions]
user adds / deletes / edits descriptions
        │  POST /api/confirm   { descriptions: [...] }
        ▼
[Block 3 — Translation agent, LLM]
extract 3–6 keywords from corrected descriptions
        │  { description, keyWord: [...] }
        ▼
[Block 2 — Data-Engineer agent]
return historical monthly time series + metadata (mock now)
        │  { timeseries_metadata, timeseries }
        ▼
[Block 4 — Sybilion + report agent]
build Sybilion request → forecast (SDK) → fetch prediction
then LLM writes & executes Python → report
        │  { drivers, expected_revenue, graphs, investment_cost, decision, reason }
        ▼
[Front-End — Results Dashboard]
verdict · revenue/cost · forecast chart w/ bands · drivers · investment · reason
```

---

## 4. HTTP routes

The frontend talks to the backend through these routes. (Internal agent-to-agent
calls — translation → data-engineer, report → Sybilion — use the JSON shapes in
`FLOW_AND_AGENTS.md` §4.)

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/extract` | `{ userInput }` → `{ descriptions: [...] }` (Block 3a) |
| `POST` | `/api/confirm` | `{ descriptions: [...] }` → triggers pipeline, returns `{ job_id }` (Block 3b → 2 → 4) |
| `GET`  | `/api/status/{job_id}` | pipeline step + progress (poll ~3 s) |
| `GET`  | `/api/result/{job_id}` | final report JSON once done |
| `GET`  | `/api/health` | health check |

> The confirm→result path is async because the Sybilion forecast is async. The
> frontend polls `/api/status` and then fetches `/api/result`. If a synchronous
> path is simpler for the prototype, Block 4 may return the report directly from
> `/api/confirm` — but **Block 1 must support the polling path**, since the
> forecast can take minutes. Agree the final choice during integration; default
> is polling.

---

## 5. Canonical JSON contracts

These mirror `FLOW_AND_AGENTS.md`. Match field names exactly.

### 5.1 `POST /api/extract`
Input:
```json
{ "userInput": "I want to open an ice cream shop in Vienna's 1st district." }
```
Output:
```json
{ "descriptions": [
  "Average rent for a small retail location in Vienna's 1st district",
  "Monthly tourism footfall in central Vienna",
  "Seasonal demand pattern for frozen desserts in Austria"
] }
```

### 5.2 `POST /api/confirm`
Input (user-corrected descriptions):
```json
{ "descriptions": ["Average rent for a small retail location…", "…"] }
```
Output:
```json
{ "job_id": "abc-123" }
```

### 5.3 `GET /api/status/{job_id}`
```json
{ "job_id": "abc-123", "step": "forecasting", "progress": 0.6, "done": false }
```
`step` ∈ `extracting` · `fetching` · `forecasting` · `reporting` · `done`.

### 5.4 Data-Engineer contract (Block 3 → Block 2)
Request:
```json
{ "description": "Average Revenue of Icecreamshops in Vienna with filter",
  "keyWord": ["icecream", "weather"] }
```
Response:
```json
{
  "timeseries_metadata": {
    "title": "Average Revenue of Icecreamshops in Vienna with filter",
    "description": "Average Revenue of Icecreamshops in Vienna with filter.",
    "keywords": ["icecream", "restaurants", "weather", "seasons"]
  },
  "timeseries": {
    "2021-12-01": 218.5, "2022-01-01": 148.1, "2022-02-01": 145.9,
    "2022-03-01": 162.4, "2022-04-01": 168.7, "2022-05-01": 166.2
  }
}
```

### 5.5 Sybilion request (Block 4 builds from §5.4)
```json
{
  "pipeline_version": "v1",
  "frequency": "monthly",
  "soft_horizon": 6,
  "recency_factor": 0.5,
  "timeseries_metadata": { "title": "…", "description": "…", "keywords": ["…"] },
  "timeseries": { "2021-12-01": 218.5, "…": "…" }
}
```

### 5.6 Final report contract (`GET /api/result/{job_id}` → Front-End)
This is what Block 1 renders. Block 4 produces it.
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
  }
}
```

> Notes:
> - `decision.label` ∈ **Launch · Adapt concept · Delay · Do not launch** —
>   drive verdict color from this.
> - `graphs.*` points carry `historical`, `forecast`, `low`, `high` so the chart
>   shows history, the forecast continuation, and the confidence band.
> - `backtest` is surfaced on the dashboard and feeds `decision.confidence`
>   (better backtest → higher confidence). The jury rewards backtest discipline.
> - `drivers[].horizon` lets the UI show how importance shifts across the
>   forecast horizon (month 1 vs month 6).

---

## 6. File structure

```
marketpilot/
├── backend/
│   ├── main.py                 ← FastAPI app, routes (orchestration)
│   ├── translation_agent.py    ← Block 3: descriptions + keywords (Featherless LLM)
│   ├── data_engineer.py        ← Block 2: time-series endpoint (mock now)
│   ├── sybilion_client.py      ← Block 4: Sybilion SDK wrapper + fallback
│   ├── report_agent.py         ← Block 4: LLM writes & executes Python → report
│   ├── contracts.py            ← shared Pydantic models for all JSON shapes
│   └── requirements.txt
├── frontend/                   ← Block 1: React + TypeScript (already scaffolded)
│   └── src/...
├── tests/
│   ├── test_data_engineer.py
│   ├── test_sybilion_client.py
│   └── test_report_agent.py
├── mock/
│   ├── timeseries_icecream.json   ← Data-Engineer mock
│   ├── forecast.json              ← cached real Sybilion forecast (fallback)
│   └── result.json                ← full report mock for the frontend
└── README.md
```

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sybilion forecast job > a few min | Medium | High | Block 4 caches a real forecast to `mock/forecast.json`; UI shows polling step labels |
| No real time series found | Medium | Medium | Block 2 returns documented mock data |
| LLM returns malformed JSON / bad Python | Medium | Medium | Report agent retries once with stricter prompt; falls back to a deterministic calc |
| Contract drift between blocks | Medium | High | Contracts fixed in `FLOW_AND_AGENTS.md`; each block exposes one clean interface |
| API keys missing | Low | High | Featherless + Sybilion keys checked at startup with clear errors; mock fallback otherwise |

---

## 8. Environment

```bash
export FEATHERLESS_API_KEY=...     # translation + report LLM
export SYBILION_API_TOKEN=...      # Sybilion SDK (optional → mock fallback)
```
