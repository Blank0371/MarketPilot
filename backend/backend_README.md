# MarketPilot — Backend

Python backend for **MarketPilot** (*Navigate uncertainty before you launch*) — a
decision agent built on top of the **Sybilion** probabilistic forecasting API.
A user types a business idea; the backend turns it into a transparent launch
verdict (**Launch · Adapt concept · Delay · Do not launch**) with the numbers
behind it.

> **Docs to read first:** `../CLAUDE.md` (entry point) → `../ARCHITECTURE.md`
> (system wiring) → `../MODEL.md` (the decision model). This README is the
> practical run/dev guide; those files are the source of truth.

---

## What this backend does

One synchronous endpoint runs the whole pipeline:

```
POST /api/analyze  { userInput, forecast_horizon_months? }
   → Translation agent (LLM): idea → descriptions → keywords + title
   → Data-Engineer:           keywords → historical monthly time series
   → Sybilion client:         time series → probabilistic forecast (+ drivers, backtest)
   → Report agent (MODEL.md): profiler(LLM) → params → indices → economics
                              → multi-dimensional decision → reason(LLM)
   → report JSON  (ARCHITECTURE.md §5.6)
```

The numbers and the verdict are **deterministic Python**. The LLM only classifies
the business (profiler) and phrases the reason — it never invents a number. See
`../MODEL.md` §0.

---

## Modules

| File | Block | Responsibility |
|------|-------|----------------|
| `main.py` | orchestrator | FastAPI app; `/api/analyze` (synchronous pipeline), `/report/recompute`, `/api/health` |
| `translation_agent.py` | 3 | idea → descriptions, descriptions → keywords + title (Featherless LLM, strict-JSON + fallback) |
| `data_engineer.py` | 2 | historical monthly time-series endpoint; LLM profiler + deterministic series generator (mock series for now) |
| `sybilion_client.py` | 4 | Sybilion SDK wrapper (submit → poll → fetch artifacts); synthetic fallback; artifact parsing |
| `report_agent.py` | 4 | the decision model (`../MODEL.md`): profiler, parameter cascade, indices, economics, multi-dimensional verdict, reason |
| `intent_extractor.py` | 2 | (v2.0) simplified copy from the big data-engineer agent; extracts location/type to help the profiler |
| `contracts.py` | shared | Pydantic models for the JSON shapes in `ARCHITECTURE.md` §5 |

---

## Setup

Python 3.12 recommended.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

```bash
export FEATHERLESS_API_KEY=...     # translation + profiler + report LLM
export SYBILION_API_TOKEN=...      # Sybilion SDK (optional → synthetic fallback in prod)
export MODEL_MODE=prod             # dev | prod  (see "Run modes"); default prod
```

A repo-root `.env` is auto-loaded on import (see `__init__.py`); shell variables
take precedence. Copy `.env-example` to `.env` for local dev.

---

## Run

```bash
# from the repo root, with the venv active
uvicorn backend.main:app --reload --port 8000
```

Then:

```bash
# health
curl http://127.0.0.1:8000/api/health

# full analysis (synchronous — returns the whole report)
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"userInput": "ice cream shop in Vienna 1st district", "forecast_horizon_months": 6}'

# live what-if (reuses the cached forecast, no Sybilion call)
curl -X POST http://127.0.0.1:8000/report/recompute \
  -H "Content-Type: application/json" \
  -d '{"userInput": "ice cream shop in Vienna", "overrides": {"monthly_rent_eur": 11000}}'
```

Individual blocks can still be run standalone for debugging (each module defines
its own `app`), e.g. `uvicorn backend.data_engineer:app --port 8002`. The
demo uses the orchestrator on port 8000.

---

## Run modes (dev / prod)

Set by `MODEL_MODE` (see `../MODEL.md` §1.1):

- **`dev` — no fallbacks.** If the LLM does not answer, Sybilion is unavailable,
  or any step fails → an **error is raised**. Use this while developing so silent
  stubs don't hide bugs.
- **`prod` — loud fallbacks.** A synthetic Sybilion forecast, a neutral profiler
  profile, a deterministic reason template. Every fallback that fires is recorded
  in the report's `runtime.fallbacks` and shown to the user/jury. Use this for
  the live demo (must never crash).

The report's `runtime` block reports the active mode and any fallbacks that fired:
```json
"runtime": { "mode": "prod", "fallbacks": ["sybilion_unavailable->synthetic_forecast"] }
```

---

## Seeding the Sybilion cache (recommended before the demo)

The first real Sybilion response is cached under `mock/` so later runs (and the
demo) reuse it. To seed it with a real token:

```bash
SYBILION_API_TOKEN=... python -m backend.sybilion_client --seed
```

This writes `mock/forecast.json`, `mock/external_signals.json`, and
`mock/backtest_metrics.json`. Without a token, the client generates a synthetic
forecast from the history (and, in `prod`, flags it). Seeding once with a real
token also reveals the real backtest **MAPE** for the chosen series.

---

## Tests

```bash
# from the repo root
pip install -r backend/requirements.txt
pytest tests/ -v
```

Useful subsets:

```bash
pytest tests/test_report_agent.py -v
pytest tests/test_sybilion_client.py -v
```

Speed/determinism flag used by some tests:
`REPORT_DISABLE_CODEGEN=1` skips the legacy economics subprocess and runs the
in-process deterministic calc only (the subprocess path is being retired in
v2.0 — the in-process calc is the single source of truth; see `../MODEL.md` §11).

---

## Notes for contributors

- **Match the contracts.** The JSON shapes in `../ARCHITECTURE.md` §5 are fixed;
  other blocks (and the frontend) depend on them. The data-engineer output is
  always `{ "YYYY-MM-DD": float }` (≥60 monthly points) regardless of how the
  series is generated.
- **Every decision-model number references `../MODEL.md`.** Add a
  `# see MODEL.md §X.Y` comment next to any hard-coded coefficient. The §10
  correspondence table in `MODEL.md` is the review checklist.
- **The forecast horizon is a request parameter** (`forecast_horizon_months`,
  default 6, range 1–12), passed to Sybilion as `soft_horizon` — not a hard-coded
  constant (`../MODEL.md` §2.2).
- **Quantiles** from Sybilion are read from `quantile_forecast` keys
  `"0.1"`/`"0.5"`/`"0.9"` — never `p10/p50/p90`.
- The big standalone `data-engineer-agent/` project (Eurostat/Yahoo/registry) is
  a **roadmap component**, not on the demo path. The demo uses
  `backend/data_engineer.py`. If a real source is wired in later, a relevance
  filter must reject non-demand metrics (e.g. inflation) before they reach the
  report model.
