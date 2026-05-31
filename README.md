# MarketPilot

> **Navigate uncertainty before you launch.**

A forecasting-driven **decision agent** for future business owners and the investors who back them. Type a business idea in plain language and MarketPilot turns a probabilistic market forecast into a transparent **go / no-go** recommendation — with the numbers, drivers, and reasoning all on the table.

Built for **Zero One Hack, Vienna · May 2025** — Track 3: *Forecasting AI* (Challenge owner: **Sybilion**).

**Stack:** Python · FastAPI · TanStack Start · React · TypeScript · Sybilion Forecasting API · Featherless LLM

---

## What it does

Founders have ideas; they rarely have a defensible answer to *"will this actually work, here, right now?"* Investors face the mirror image: a pitch deck and a gut feeling. MarketPilot sits between the two.

You describe an idea in free text — for example:

> "I want to open an ice cream shop in Vienna's 1st district."

MarketPilot then:

1. extracts the **quantifiable factors** behind the idea (rent, foot traffic, seasonality, margin, tourism dependency, …) and lets you edit them,
2. pulls a **historical monthly time series** for the relevant market signal,
3. runs a **probabilistic forecast** through the Sybilion API (downside / base / upside, with confidence bands and driver importance),
4. computes the economics — expected revenue, costs, investment, break-even probability, payback — and returns a clear verdict:

| Verdict | Meaning |
|---|---|
| **Launch** | Economically attractive under current assumptions. |
| **Adapt concept** | Real potential, but the current concept is too risky — adjust it. |
| **Delay / change location** | Could work, but not under current conditions or at this location. |
| **Do not launch** | Not attractive under current assumptions. |

The point is not just the label. It's the **visible reasoning** behind it — and the ability to change an assumption live (rent goes up, basket size goes up) and watch the recommendation move.

---

## Who it's for

MarketPilot serves two sides of the same decision. The numbers and reasoning are identical; what differs is the question being asked.

**Aspiring business owners** — to pressure-test an idea before committing capital: is the demand there, is the location right, where does it break even, and what would need to change to make it viable.

**Investors (VCs, angels, family offices)** — for **investment risk evaluation**: an independent second opinion on a pitched venture, grounding gut feeling in a probabilistic demand forecast, explicit downside/upside scenarios, and a transparent break-even probability rather than a founder's projections alone.

**Banks and lenders** — for **loan and credit evaluation**: assessing the viability of a small-business or location-based venture before extending financing, with a traceable, reproducible verdict and visible driver analysis that can be attached to a credit file.

In every case the value is the same: a forecast plus a driver list does not, by itself, change a decision. MarketPilot turns probabilistic market signals into a defensible **go / no-go** call — with the reasoning legible to a non-expert and reproducible enough to stand up to scrutiny.

---

## How it works

```
User types a free-text business idea
        │
        ▼
Translation agent (LLM)   →  extracts standardized DESCRIPTIONS of the
        │                    quantifiable factors (rent, footfall, seasonality…)
        ▼
        (user edits / confirms the descriptions in the UI)
        │
        ▼
Translation agent (LLM)   →  derives 3–6 forecasting KEYWORDS
        │
        ▼
Data-Engineer agent       →  returns a historical monthly time series + metadata
        │
        ▼
Sybilion API              →  probabilistic forecast: p10 / p50 / p90,
        │                    confidence bands, driver importance, backtest metrics
        ▼
Decision engine           →  expected revenue, costs, investment, break-even
        │                    probability, risk-adjusted profit → verdict + reason
        ▼
Frontend dashboard        →  forecast chart · drivers · financials · verdict
        │
        ▼
What-if controls          →  change an assumption, recompute, compare before/after
```

The standardized factors the agent reasons over are **rent, staff costs, location foot traffic, average basket price, margin, seasonality, and tourism dependency** — each one rephrased to fit the specific idea.

---

## Tech stack

**Frontend** (`frontend/`, port `5173`)
- React 19 + TypeScript on **TanStack Start** (file-based routing, Vite)
- Tailwind CSS v4 + **shadcn/ui** (Radix primitives)
- Recharts for forecast/driver visualizations, Framer Motion for transitions
- Ships with an offline mock mode so the dashboard runs without a backend

**Backend** (`backend/`, ports `8002` + `8003`)
- Python + **FastAPI** + Pydantic, served by Uvicorn
- **Translation agent** (`:8003`) — idea → descriptions → keywords; orchestrates the pipeline
- **Data-Engineer agent** (`:8002`) — historical monthly time-series provider
- LLM calls via **Featherless** (OpenAI-compatible; Llama 3.1 8B by default), with a deterministic mock fallback when no key is set
- Forecasting via the **Sybilion** Python SDK

---

## Project structure

```
ZeroOneHack_01/
├── backend/
│   ├── translation_agent.py    # idea → descriptions → keywords; pipeline orchestrator (:8003)
│   ├── data_engineer.py        # historical monthly time-series endpoint (:8002)
│   ├── report_agent.py         # decision-report producer (decision engine)
│   ├── sybilion_client.py      # Sybilion forecast wrapper + synthetic fallback
│   ├── requirements.txt
│   └── MODEL.md                # decision-model specification
├── frontend/                   # TanStack Start + React + TS dashboard (:5173)
│   └── src/lib/                # api.ts, mockApi.ts, mockData.ts, types.ts
├── data-engineer-agent/        # standalone real data-engineer service (roadmap)
├── mock/                       # committed mock series, forecast, drivers, backtest (fallbacks)
├── tests/                      # pytest suite for the backend agents
├── start.sh                    # launches both backend agents + the frontend
├── .env-example                # copy to .env for local secrets
├── ARCHITECTURE.md             # system wiring (canonical)
├── FLOW_AND_AGENTS.md          # product flow + agent contracts
├── FOR_DEVELOPERS.md           # detailed setup & runbook
└── README.md                   # this file
```

---

## Getting started

### Prerequisites
- Python 3.11+
- Node.js 18+ (npm; **bun** also works — the repo includes a `bun.lock`)

### 1. Clone and configure

```bash
git clone https://github.com/stnleey/ZeroOneHack_01.git
cd ZeroOneHack_01
cp .env-example .env   # fill in keys if you have them — optional, see below
```

### 2. Install backend dependencies

`start.sh` expects the virtualenv at `env/` (it falls back to `.venv/`):

```bash
python3 -m venv env
source env/bin/activate
pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install        # or: bun install
cd ..
```

### 4. Run everything

```bash
./start.sh
```

This launches the Data-Engineer agent (`:8002`), the Translation agent (`:8003`), and the frontend dev server (`:5173`), and stops them all on `Ctrl+C`. Then open:

```
http://localhost:5173
```

Ports are overridable:

```bash
DATA_ENGINEER_PORT=8012 TRANSLATION_PORT=8013 FRONTEND_PORT=5174 ./start.sh
```

### Running services individually

```bash
# backend agents (separate terminals)
source env/bin/activate
uvicorn backend.data_engineer:app --reload --port 8002
uvicorn backend.translation_agent:app --reload --port 8003

# frontend
cd frontend && npm run dev
```

---

## Configuration

Copy `.env-example` to `.env` (auto-loaded by the backend on import; real shell variables take precedence). **All keys are optional** — without them, MarketPilot runs on deterministic mock fallbacks, so the demo works offline.

| Variable | Required | Description |
|---|---|---|
| `FEATHERLESS_API_KEY` | No | Featherless LLM key. Missing → deterministic mock extraction/judgment. |
| `FEATHERLESS_BASE_URL` | No | OpenAI-compatible base URL. Default `https://api.featherless.ai/v1`. |
| `FEATHERLESS_MODEL` | No | Default `meta-llama/Meta-Llama-3.1-8B-Instruct`. |
| `SYBILION_API_TOKEN` | No | Sybilion forecast token. Missing → synthetic forecast fallback. |
| `DATA_ENGINEER_URL` | No | URL of a separately running Data-Engineer service. Missing → in-process call. |
| `MODEL_MODE` | No | `dev` (fail loudly, no fallbacks) or `prod` (loud fallbacks). Default `prod` for the demo. |

---

## API overview

| Service (port) | Method | Route | Purpose |
|---|---|---|---|
| Translation (`:8003`) | `POST` | `/api/extract` | `{ userInput }` → `{ descriptions }` |
| Translation (`:8003`) | `POST` | `/api/confirm` | confirmed descriptions → verdict + forecast summary |
| Translation (`:8003`) | `POST` | `/api/refine` | next-round refinement (live what-if at the idea level) |
| Translation (`:8003`) | `GET` | `/health` | health + LLM / Sybilion availability |
| Data-Engineer (`:8002`) | `POST` | `/data/timeseries` | `{ description, keyWord[] }` → time series + metadata |
| Data-Engineer (`:8002`) | `GET` | `/health` | health check |

Quick smoke test:

```bash
curl -X POST http://localhost:8003/api/extract \
  -H "Content-Type: application/json" \
  -d '{"userInput":"I want to open an ice cream shop in Vienna'\''s 1st district."}'
```

Full request/response contracts live in `ARCHITECTURE.md` and `FLOW_AND_AGENTS.md`.

---

## Testing

```bash
source env/bin/activate
pytest -q
```

---

## Live demo script

A 60-second walkthrough for the stage:

1. **Load the default scenario** — ice cream shop, Vienna 1st district.
2. **Run the analysis** — forecast with confidence bands, driver importance, break-even probability, expected monthly profit, and a verdict appear.
3. **First recommendation** — e.g. *Adapt concept*: strong tourism-driven demand, but high rent and seasonality make a pure retail concept risky.
4. **Change an assumption live** — raise monthly rent from €8,000 to €13,000.
5. **The agent reacts** — break-even probability drops, the verdict shifts toward *Do not launch / change location*.
6. **Improve the concept** — raise the average basket size and add tasting revenue; the verdict recovers toward *Adapt concept / Launch*.

This shows the three things that matter: the forecast drives the decision, the reasoning is visible, and the agent adapts when an assumption shifts.

---

## Project status & roadmap

This is an active hackathon prototype. The live demo path runs the full idea → forecast → verdict loop end-to-end. Work in progress / planned:

- Converging the verdict fully onto the deterministic decision model in `report_agent.py` (see `backend/MODEL.md`).
- Wiring the standalone `data-engineer-agent/` (real sources: Eurostat, commodities, …) in place of the mock series.
- Multi-location comparison (e.g. Vienna 1st vs 7th vs 16th district) and additional business types (café, gym, bakery, coworking, …).

See `ARCHITECTURE.md` for the detailed current-vs-target breakdown.

---

## Team & acknowledgements

Built at **Zero One Hack, Vienna (May 2025)** for the Sybilion **Forecasting AI** track.
Forecasting infrastructure provided by **Sybilion**; LLM inference via **Featherless**.

**Team**
- **Alexander Hess** — Frontend
- **Ivan Popov** — Math model development
- **Leo Solomon** — Translation agent
- **Stanislav Kononov** — Data engineering

---

## License

Licensed under the **Business Source License 1.1** (Licensor: *Market Pilot — Serebro*, © 2025). The Licensed Work may be copied and redistributed for **non-production purposes only**, unmodified; production use, offering it as a service, sublicensing, or creating derivative works requires a separate written agreement from the Licensor. On the **Change Date (2031-01-01)** the license converts to the **MIT License**. See [`LICENSE`](./LICENSE) for the full terms.