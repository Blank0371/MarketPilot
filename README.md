# MarketPilot

MarketPilot is a forecast-driven decision application for evaluating location-based business ideas.

Current runnable stack:
- `backend.data_engineer` (FastAPI, port `8002`)
- `backend.translation_agent` (FastAPI, port `8003`)
- `frontend` (TanStack Start, port `5173`)

This README reflects the **current code/runtime behavior**.

---

## 1. What is implemented now

- Idea input -> description extraction (`/api/extract`)
- Description confirmation -> translation pipeline (`/api/confirm`)
- Data-engineer time-series endpoint (`/data/timeseries`)
- Frontend dashboard connected to backend pipeline (`:8003`)

---

## 2. Prerequisites

- Python 3.11+
- Node.js 18+
- `npm`

---

## 3. Setup

From repo root:

```bash
python3 -m venv env
source env/bin/activate
pip install -r backend/requirements.txt
```

Frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Environment file:

```bash
cp .env-example .env
```

---

## 4. Environment variables

### Required for a meaningful end-to-end backend run

- `FEATHERLESS_API_KEY`  
  Required if you want LLM-based extraction/routing instead of deterministic fallback behavior.

### Optional but recommended

- `FEATHERLESS_BASE_URL` (default: `https://api.featherless.ai/v1`)
- `FEATHERLESS_MODEL`
- `REAL_DATA_ENABLED` (default in code is `true`)
- `DATA_ENGINEER_URL` (only if translation agent should call an external DE service instead of in-process)

### Notes on keys and behavior

- The application can start without API keys.
- Without LLM/network availability, many requests fall back to deterministic mock/proxy behavior.
- If you want to validate real-source usage, you need working network access and valid keys.

---

## 5. Run application

### One-command startup

```bash
./start.sh
```

Starts:
- Data Engineer: `http://localhost:8002`
- Translation Agent: `http://localhost:8003`
- Frontend: `http://localhost:5173`

Stop with `Ctrl+C`.

### Port overrides

```bash
DATA_ENGINEER_PORT=8012 TRANSLATION_PORT=8013 FRONTEND_PORT=5174 ./start.sh
```

---

## 6. Run services manually

Terminal 1:

```bash
source env/bin/activate
uvicorn backend.data_engineer:app --reload --port 8002
```

Terminal 2:

```bash
source env/bin/activate
uvicorn backend.translation_agent:app --reload --port 8003
```

Terminal 3:

```bash
cd frontend
npm run dev
```

---

## 7. Frontend

Frontend and backend are wired in the running app flow.

---

## 8. API smoke tests

### Data Engineer health

```bash
curl http://localhost:8002/health
```

### Translation health

```bash
curl http://localhost:8003/health
```

### Data Engineer request

```bash
curl -s -X POST http://localhost:8002/data/timeseries \
  -H "Content-Type: application/json" \
  -d '{"description":"Get CPI inflation in Austria for the last 10 years"}' | jq
```

### Translation extract

```bash
curl -s -X POST http://localhost:8003/api/extract \
  -H "Content-Type: application/json" \
  -d '{"userInput":"I want to launch a wine tasting studio with retail sales in Vienna."}' | jq
```

### Translation confirm

```bash
curl -s -X POST http://localhost:8003/api/confirm \
  -H "Content-Type: application/json" \
  -d '{"descriptions":["Tourism seasonality in Vienna","Labor costs in Austria","CPI trends in Austria"]}' | jq
```

---

## 9. Real vs mock diagnostics

For `backend.data_engineer`, check logs:

- Real source path:
  - `REAL_SOURCE_USED ... path=llm_selection`
  - `REAL_SOURCE_USED ... path=planner`
- Mock fallback path:
  - `data_engineer provenance=MOCK ...`

This is the fastest way to verify whether a request used a real provider or fallback.

---

## 10. Tests

Run all tests:

```bash
source env/bin/activate
pytest -q
```

Run Data Engineer tests only:

```bash
source env/bin/activate
pytest -q tests/test_data_engineer.py
```

---

## 11. Repository pointers

- Backend architecture doc: `backend/TECHNICAL_ARCHITECTURE.md`
- Backend runtime code:
  - `backend/data_engineer.py`
  - `backend/translation_agent.py`
  - `backend/data_engineer_core/`
- Frontend entry route:
  - `frontend/src/routes/index.tsx`

---

## 12. Team

- Alexander Hess — Frontend
- Ivan Popov — Math model development
- Leo Solomon — Translation agent
- Stanislav Kononov — Data engineering
