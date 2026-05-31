# For Developers

This file is the practical setup and runbook for working on MarketPilot.

## Project Shape

MarketPilot is currently split into:

- `backend/data_engineer.py` — FastAPI Data-Engineer agent. Returns a mock 60-month seasonal ice cream time series.
- `backend/translation_agent.py` — FastAPI Translation agent. Extracts descriptions and keywords via Featherless, with deterministic fallback when no API key is present.
- `frontend/` — React/TanStack/Vite frontend connected to the backend pipeline.
- `mock/` — committed mock data used by backend agents.
- `tests/` — Python tests for the implemented backend agents.

## Environment Variables

Copy the example file and fill in local secrets:

```bash
cp .env-example .env
```

The backend loads `.env` automatically via `python-dotenv` when importing the `backend` package. Real environment variables already set in the shell or deployment environment take precedence over `.env`.

Current variables:

| Variable | Required | Used by | Description |
| --- | --- | --- | --- |
| `FEATHERLESS_API_KEY` | No | `backend/translation_agent.py` | Featherless API key for LLM calls. If missing, the translation agent uses deterministic mock fallback output. |
| `FEATHERLESS_BASE_URL` | No | `backend/translation_agent.py` | OpenAI-compatible Featherless base URL. Defaults to `https://api.featherless.ai/v1`. |
| `FEATHERLESS_MODEL` | No | `backend/translation_agent.py` | Featherless model name. Defaults to `meta-llama/Meta-Llama-3.1-8B-Instruct`. |
| `DATA_ENGINEER_URL` | No | `backend/translation_agent.py` | Optional URL for a separately running Data-Engineer service, e.g. `http://localhost:8002`. If missing, translation calls `backend.data_engineer.get_timeseries()` in-process. |
| `SYBILION_API_TOKEN` | Future | Block 4 / Sybilion client | Sybilion API token. Documented for the planned forecast client, but not used by committed backend code yet. |

## Backend Setup

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run tests:

```bash
pytest -q
```

## Running Backend Agents

Run the Data-Engineer agent:

```bash
source .venv/bin/activate
uvicorn backend.data_engineer:app --reload --port 8002
```

Health check:

```bash
curl http://localhost:8002/health
```

Example request:

```bash
curl -X POST http://localhost:8002/data/timeseries \
  -H "Content-Type: application/json" \
  -d '{"description":"Average revenue of ice cream shops in Vienna","keyWord":["icecream","vienna","weather"]}'
```

Run the Translation agent:

```bash
source .venv/bin/activate
uvicorn backend.translation_agent:app --reload --port 8003
```

Health check:

```bash
curl http://localhost:8003/health
```

Example extract request:

```bash
curl -X POST http://localhost:8003/api/extract \
  -H "Content-Type: application/json" \
  -d '{"userInput":"I want to open an ice cream shop in Vienna'\''s 1st district."}'
```

Example confirm request:

```bash
curl -X POST http://localhost:8003/api/confirm \
  -H "Content-Type: application/json" \
  -d '{"descriptions":["Average rent for a small retail location in Vienna","Monthly tourism foot traffic in central Vienna","Seasonal demand pattern for ice cream in Austria"]}'
```

## Frontend Setup

From `frontend/`:

```bash
npm install
npm run dev
```

Open the URL printed by Vite, usually:

```text
http://localhost:5173
```

Build:

```bash
npm run build
```

Lint:

```bash
npm run lint
```

Important: frontend run path is backend-connected at `http://127.0.0.1:8003`.

## Current Local Demo Paths

One-command startup (recommended):

```bash
./start.sh
```

The script starts both backend agents and the frontend dev server, and stops all of them on `Ctrl+C`.

Port overrides:

```bash
DATA_ENGINEER_PORT=8012 TRANSLATION_PORT=8013 FRONTEND_PORT=5174 ./start.sh
```

Prerequisites for `start.sh`:

- Python virtualenv at `env/` with backend dependencies installed
- frontend dependencies installed (`frontend/node_modules`)

For the visual frontend demo:

```bash
cd frontend
npm install
npm run dev
```

For backend agent development:

```bash
pytest -q
uvicorn backend.data_engineer:app --reload --port 8002
uvicorn backend.translation_agent:app --reload --port 8003
```

Run the two `uvicorn` commands in separate terminals.

## Notes

Canonical product flow and contracts are documented in `FLOW_AND_AGENTS.md` and `ARCHITECTURE.md`.
