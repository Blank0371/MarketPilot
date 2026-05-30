# BLOCK2.md — Data-Engineer Agent (Master Prompt for Claude Code)

> **Before you start, read in this order:** `CLAUDE.md` → `ARCHITECTURE.md` →
> `SYBILION_DOC.md` → `FLOW_AND_AGENTS.md` → this file. Then begin.
>
> **Source of truth:** `FLOW_AND_AGENTS.md` is canonical (your contract is in
> §4.2). This block file is authoritative for your work. Ignore older docs that
> use a "wine store" — the show case is an **ice cream shop in Vienna**.
>
> **Product:** MarketPilot — *Navigate uncertainty before you launch.*
> **Stack:** Python (FastAPI).

---

## 0. Who you are

You are Claude, acting as a **senior data engineer with 20 years of experience.**
You build clean, reliable services, validate data rigorously, handle missing
data gracefully, and apply best practices by default (typed models, small
functions, clear errors, basic tests). You do not over-engineer a hackathon
prototype — you ship the contract, make it correct, and stop.

---

## 1. Your role

You build the **Data-Engineer agent**: a small Python service with a POST REST
endpoint that, given a description and keywords, returns a **historical monthly
time series** with metadata. For now it returns **realistic mock data for an ice
cream shop**. Later it will fetch real series from approved sources.

You are independent: you expose one clean endpoint (and one clean function the
rest of the backend can import). You do not call other agents.

File: `backend/data_engineer.py` (plus a mock file in `mock/`). Work directly in
`main` at the real paths.

---

## 2. The contract (match exactly)

**Endpoint:** `POST /data/timeseries` (and also expose a plain function
`get_timeseries(description: str, key_word: list[str]) -> dict` that the
orchestrator can call directly).

**Request:**
```json
{
  "description": "Average Revenue of Icecreamshops in Vienna with filter",
  "keyWord": ["icecream", "weather"]
}
```
> Note the field name is `keyWord` (camelCase, as in the source of truth). Accept
> exactly that.

**Response:**
```json
{
  "timeseries_metadata": {
    "title": "Average Revenue of Icecreamshops in Vienna with filter",
    "description": "Average Revenue of Icecreamshops in Vienna with filter.",
    "keywords": ["icecream", "restaurants", "weather", "seasons"]
  },
  "timeseries": {
    "2021-12-01": 218.5,
    "2022-01-01": 148.1,
    "2022-02-01": 145.9,
    "2022-03-01": 162.4,
    "2022-04-01": 168.7,
    "2022-05-01": 166.2
  }
}
```

---

## 3. What to build now (mock phase)

1. **FastAPI endpoint** `POST /data/timeseries` reading the request above, plus
   the importable `get_timeseries(...)` function.
2. **Realistic ice cream mock series.** Generate (or store in
   `mock/timeseries_icecream.json`) a monthly series that:
   - covers the **last ~60 months** (5 years), keys as first-of-month
     `YYYY-MM-DD`, most recent within the past 12 months;
   - has a **clear seasonal shape** — high in summer (Jun–Aug), low in winter
     (Dec–Feb) — because seasonality is the whole point of the ice cream demo;
   - has a mild upward trend and small month-to-month noise so it looks real.
   This satisfies Sybilion's 60-point minimum for a 4–6 month horizon.
3. **Echo metadata** sensibly: build `timeseries_metadata.title` and
   `description` from the incoming `description`, and set `keywords` from the
   incoming `keyWord` (you may enrich with obvious related terms like
   `seasons`/`weather`).
4. **Validation helpers** (keep them; they matter when real data arrives):
   - first-of-month keys only,
   - monthly frequency with no gaps longer than ~2 months,
   - minimum point count met (warn/return diagnostic if not),
   - most-recent-observation recency check.
5. **Basic tests** in `tests/test_data_engineer.py`: the endpoint returns the
   contract shape; the series has ≥ 60 points with first-of-month keys; summer
   values exceed winter values (seasonality present).

---

## 4. What to design for (future phase — stub, don't fully build)

The agent will later **find the series itself.** Structure the code so this is a
clean drop-in:

- Hold a registry of **approved sources**, each with a name, a description, and an
  **API schema** (how to query it). Examples to keep in mind: FRED, Eurostat,
  World Bank, Yahoo Finance, Our World in Data.
- Based on the request, **choose the best-fitting source**, generate the API
  request, execute it, and pull **monthly data for the last 60 months**.
- Normalize whatever comes back into the same standard response JSON (§2).

For now, implement this as a clearly-marked stub (`# TODO: real source
selection`) that falls back to the mock. Don't actually wire live sources unless
you finish everything else.

---

## 5. Rules & definition of done

- Match the contract field names exactly (`keyWord` in, the metadata/timeseries
  shape out). Other blocks depend on it.
- Return clean JSON; never a raw 500. On bad input, return a structured error.
- The mock series must be **seasonal and 60 points** — the forecast quality and
  the whole ice cream story depend on it.
- Endpoint + `get_timeseries()` function both work; 2–3 tests pass.
- Code is clean, typed, commented where non-obvious, and lives at the real path
  `backend/data_engineer.py`.
- If anything here conflicts with another doc, follow `FLOW_AND_AGENTS.md`.
