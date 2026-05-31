# REPORT — MarketPilot

## TL;DR
MarketPilot is a decision-support pipeline for evaluating location-based retail ideas before launch.  
It converts business assumptions into a structured report with forecast signals, financial estimates, and a deterministic recommendation (`Launch`, `Adapt concept`, `Delay`, `Do not launch`).  
Current status: backend pipeline is working and tested; frontend integration is partial.

## Problem
Founders usually lack a reproducible way to answer: should this business launch at this location under these costs?  
We solved this by combining forecast uncertainty with deterministic economics instead of relying on plain LLM summaries.

## Approach
- Multi-stage backend flow: translation (`/api/extract`, `/api/confirm`) -> data-engineer (`/data/timeseries`) -> report computation.
- Deterministic decision logic: revenue/cost/profit, break-even probability, risk, and confidence are computed in Python.
- Stable report schema for frontend and tests: `decision`, `expected_revenue`, `graphs`, `drivers`, `backtest`, `reason`.
- Fallback-first runtime: when external dependencies fail, pipeline still returns structured output with deterministic fallback data.
- What-if recompute path for changing key assumptions (rent, basket price, margin) without rerunning full forecast retrieval.

## How to run it
- Python 3.11+
- Node.js 18+
- `npm`

```bash
python3 -m venv env
source env/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

Optional:
```bash
cp .env-example .env
```

```bash
./start.sh
```

Health checks:
```bash
curl http://localhost:8002/health
curl http://localhost:8003/health
```

Pipeline request example:
```bash
curl -sS -X POST http://localhost:8003/api/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "descriptions": [
      "Average rent for a small retail location in Vienna",
      "Monthly tourism foot traffic in central Vienna",
      "Seasonal demand pattern for ice cream in Austria"
    ]
  }'
```

## Results
- End-to-end backend path works from `descriptions` input to final recommendation report.
- Report output includes recommendation, financial projection, downside/upside, drivers, backtest quality, and graph-ready series.
- Core modules are covered by tests:
  - `tests/test_data_engineer.py`
  - `tests/test_translation_agent.py`
  - `tests/test_sybilion_client.py`
  - `tests/test_report_agent.py`
- Baseline vs current:
  - Baseline: static/mock recommendation behavior
  - Current: deterministic report generation with fixed output contract and fallback resilience

## What worked / What didn’t
- Strict separation between language tasks (LLM) and numeric decision logic (deterministic Python).
- Stable JSON contracts made backend/frontend integration and testing predictable.
- Fallback behavior improved reliability under missing keys/network issues.
- Frontend is still partially mock-driven and not fully wired to live backend in all flows.
- Async orchestration path (`status/result`) is not the default runtime path yet.
- Live behavior depends on external key/network availability.

## What we’d do with another 36 hours
- Complete frontend-to-backend integration for all steps, remove remaining mock-only branches from user-facing flows.
- Standardize on one orchestrator service and formalize async job endpoints for long-running forecast tasks.
- Add evaluation harness with scenario sets and golden outputs for regression checks on decision quality.
- Expand data-engineer real-source retrieval and provenance logging to improve trust in live data paths.
- Add lightweight observability: structured request traces, error-rate dashboard, and fallback-rate tracking.

## Credits & dependencies

- Alexander Hess — Frontend
- Ivan Popov — Math model development
- Leo Solomon — Translation agent
- Stanislav Kononov — Data engineering

Libraries/frameworks:
- FastAPI, Pydantic, Uvicorn, HTTPX
- NumPy
- React, TanStack Start/Router, Vite
- Tailwind CSS, Recharts

Models/APIs/datasets:
- Featherless-hosted LLM (OpenAI-compatible interface) for extraction/routing prompts
- Sybilion forecasting interface and artifact schema (with local mock/cache fallback)
- Local committed mock datasets under `mock/`
