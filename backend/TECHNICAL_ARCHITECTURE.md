# Backend Technical Architecture

This document describes the current backend architecture in a concise, implementation-oriented way.
It focuses on components, entities, and runtime flow.
It reflects the **current code state** (not target architecture drafts).

## 1) Purpose

The backend transforms a business-oriented textual request into a normalized monthly time series and (via the translation/report layers) into a forecast-driven decision payload.

Design goals:
- Keep endpoint contracts stable.
- Prefer real data providers when available.
- Fall back to deterministic mock generation when real data is unavailable or invalid.
- Make source provenance explicit in logs.

---

## 2) Main Components

### `translation_agent.py`
Role:
- Input-language layer for idea/description processing.
- Exposes `/api/extract` and `/api/confirm`.
- Calls Data Engineer either in-process or via `DATA_ENGINEER_URL`.

Key responsibility:
- Build/normalize textual context before data retrieval.

### `data_engineer.py`
Role:
- Core time-series provider, exposed via `/data/timeseries`.
- Public function `get_timeseries(description, key_word)` is the canonical entrypoint.

Key behavior:
- Real-data-first path (when enabled).
- LLM-assisted routing with validation.
- Planner/provider fallback.
- Deterministic mock fallback as fail-safe.

### `data_engineer_core/` (vendored library core)
Role:
- In-process “fat” data-engineer logic (no separate service required).
- Contains:
  - intent extraction
  - source planning
  - adapters
  - registries
  - schemas/validation

Important adapters:
- `adapters/eurostat.py`
- `adapters/commodities.py`
- `adapters/statistik_austria.py`

### `report_agent.py`
Role:
- Decision/report model layer (separate from raw time-series retrieval).
- Builds decision payload from forecast + assumptions + profile logic.

Current integration note:
- This module exists and is usable as a standalone/report layer, but it is not
  required for the minimal `data_engineer` + `translation_agent` test path.

### `sybilion_client.py`
Role:
- Forecast integration wrapper.
- Handles submission/polling/artifact retrieval logic and fallback semantics.

---

## 3) Core Entities

### Request Entity (`TimeseriesRequest`)
Used by `/data/timeseries`:
- `description: str`
- `keyWord: list[str]` (alias-mapped to `key_word`)

### Response Entity (`TimeseriesResponse`)
Returned by `/data/timeseries`:
- `timeseries_metadata: { description: string }` (current runtime payload)
- `timeseries: { "YYYY-MM-DD": float }`

Compatibility note:
- The Pydantic response model in code still declares `title` and `keywords`,
  but current runtime metadata builder returns `description` only.

### Internal Routing Entity (`SeriesResolution`)
Internal-only resolution snapshot:
- `category`
- `source_id`
- `source_quality`
- `reason`
- `monthly_series`

### Real Data Entity (`RealDataResult`)
Produced by `data_engineer_core.provider`:
- `series`
- `status`
- `source_ref`
- `limitations`

---

## 4) Data Flow (Current)

1. Client sends `description` (+ optional `keyWord`) to `/data/timeseries`.
2. Data Engineer attempts real path:
   - Optional LLM route selection (`dataset_id`, `metric`, `source_id`) with strict whitelist validation.
   - Direct selection fetch (`fetch_by_selection`) when valid.
   - Planner/provider fetch (`fetch`) as secondary real attempt.
3. Real output is normalized to monthly keys and validated.
4. On failure/invalid output, deterministic mock generation is used.
5. Stable response contract is returned.

Current real-path precedence:
1) LLM-assisted dataset/metric selection (`fetch_by_selection`)  
2) Planner/provider selection (`fetch`)  
3) Deterministic mock fallback

---

## 5) Source Strategy

Source categories:
- **Real**: external statistical/market providers (Eurostat, Statistik Austria, Yahoo commodities).
- **Proxy**: real but indirect metrics used as business signal approximations.
- **Mock**: deterministic synthetic series used when real retrieval is not possible.

Source selection principles:
- Prefer validated real/proxy dataset mappings.
- Reject non-whitelisted LLM routing outputs.
- Never allow LLM-generated numeric series.

---

## 6) Runtime Controls

Key environment controls:
- `REAL_DATA_ENABLED` — toggles real-data-first execution path.
- `FEATHERLESS_API_KEY` — enables LLM routing assistance.
- `DATA_ENGINEER_URL` — optional external Data Engineer call target for translation agent.

Current defaults:
- `REAL_DATA_ENABLED` defaults to `true` when unset.

Operational note:
- If LLM is unavailable or unreachable, routing falls back to deterministic keyword/planner logic.
- If external data providers fail, the backend still returns a deterministic monthly series.

---

## 7) Observability

The backend logs explicit provenance markers for traceability:
- Real source usage (LLM-selected path vs planner path).
- Mock fallback path with reason.
- Validation rejection reasons for LLM routing.

Primary markers to watch:
- `REAL_SOURCE_USED ... path=llm_selection`
- `REAL_SOURCE_USED ... path=planner`
- `data_engineer provenance=MOCK ...`

This is critical for demo reliability and production diagnostics.

---

## 8) Engineering Boundaries

What this layer should do:
- Normalize request intent into data retrieval decisions.
- Produce valid monthly time-series contract reliably.

What this layer should not do:
- Make business verdict decisions directly (report layer responsibility).
- Allow unvalidated free-form dataset routing.
- Depend on network success to produce a response.

---

## 9) Quick Verification

Run Data Engineer:

```bash
uvicorn backend.data_engineer:app --reload --port 8002
```

Health check:

```bash
curl http://localhost:8002/health
```

Sample request:

```bash
curl -X POST http://localhost:8002/data/timeseries \
  -H "Content-Type: application/json" \
  -d '{"description":"Get CPI inflation in Austria for the last 10 years"}'
```
