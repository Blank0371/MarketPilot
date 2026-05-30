# SYBILION_DOC.md — Sybilion Forecasting API Reference

> Reference for the Sybilion API used by **MarketPilot**. Block 4 (the Sybilion +
> report agent) owns the client for the **Forecasts** and **Drivers** endpoints.
> All agents should understand the forecast shape because it flows through the
> pipeline into the dashboard.
>
> **Base URL:** `https://api.sybilion.dev`
> **Auth:** `Authorization: Bearer $SYBILION_API_TOKEN` on every request.
> **Money:** all monetary fields are integer **EUR cents** (`100` = €1.00).
> Billing applies only on `2xx` responses.

---

## 1. Overview of endpoints we use

| Endpoint | Mode | Purpose |
|----------|------|---------|
| `POST /api/v1/forecasts` | **Async** (job) | Submit a monthly time series → get a probabilistic forecast |
| `GET /api/v1/forecasts/{id}` | Sync | Poll job status until `completed`, then list artifacts |
| `GET /api/v1/forecasts/{id}/artifacts/{name}` | Sync | Download a result artifact file |
| `POST /api/v1/drivers` | **Sync** (no polling) | Get a ranked list of macroeconomic drivers immediately |

There are also `Alerts`, `Regions & categories`, and `Account & usage`
endpoints. We do not need them for the MVP; they are summarised at the end for
reference.

---

## 2. Forecasts (asynchronous)

A forecast is a model-generated projection of a monthly time series. The result
includes point estimates with **quantile bands**, **per-driver attributions**,
and optional **rolling-window backtest metrics**. The Sybilion pipeline selects
the most relevant macroeconomic signals and fits the best model for the series.

**Forecast jobs are asynchronous.** Submitting returns a `job_id` immediately
while the pipeline runs in the background, typically finishing within a few
minutes.

### The full flow

1. **Submit** `POST /api/v1/forecasts` with the time series + metadata → receive
   a `job_id`.
2. **Poll** `GET /api/v1/forecasts/{id}` until `status: "completed"`.
3. **Download** the artifact files listed in the completed job response.

> **Critical for our project:** because this is async and takes minutes, we call
> it sparingly. Get a forecast once, cache the result, and recompute economics
> locally in the calculator. Never block the live demo on a fresh forecast call.

---

### 2.1 Prepare the data

The time series is submitted as a JSON object: each **key is a date**, each
**value is a numeric observation**.

**Rules:**
- Keys must be `YYYY-MM-DD` and must be the **first day of the month**. Any other
  day-of-month is **rejected**.
- The most recent observation must fall within the **past 12 months**.
- Minimum number of observations depends on the forecast horizon (using
  `soft_horizon` or `hard_horizon`, whichever is larger):

  | Horizon (months) | Minimum observations |
  |------------------|----------------------|
  | 1–3 | 40 |
  | 4–6 | 60 |
  | 7–12 | 120 |

### 2.2 Request body

Store the full request body in a JSON file (e.g. `forecast_body.json`):

```json
{
  "pipeline_version": "v1",
  "frequency": "monthly",
  "recency_factor": 0.6,
  "soft_horizon": 6,
  "backtest": true,
  "timeseries_metadata": {
    "title": "Brent Crude Oil Price Monthly",
    "description": "Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.",
    "keywords": ["oil", "brent", "energy", "commodity"]
  },
  "timeseries": {
    "2021-01-01": 57.64,
    "2021-02-01": 65.02,
    "2021-03-01": 67.24,
    "...": "...",
    "2025-12-01": 76.10
  }
}
```

**Required fields:** `pipeline_version`, `frequency`, `recency_factor`,
`timeseries_metadata`, `timeseries`, and **at least one of** `soft_horizon` or
`hard_horizon`.

**`filters.limit`** controls how many drivers the pipeline considers. A higher
limit gives more candidates (better quality) but increases job time.

### 2.3 Submit

```bash
curl -sS -X POST https://api.sybilion.dev/api/v1/forecasts \
  -H "Authorization: Bearer $SYBILION_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @forecast_body.json
```

A successful submission returns **202 Accepted**:

```json
{
  "job_id": "c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d",
  "poll_url": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
}
```

Copy the `job_id` — it is needed to poll status and download artifacts.
Validation errors return **422** with one `{field, message}` detail.

### 2.4 Poll until complete

Poll `GET /api/v1/forecasts/{id}` every ~10 seconds until `status` is
`completed`. (All SDKs provide a polling helper.)

When complete, the response lists the artifacts:

```json
{
  "job_id": "c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d",
  "status": "completed",
  "eur_cents_final": 5,
  "artifacts": [
    { "name": "forecast.json",            "href": "/api/v1/forecasts/{id}/artifacts/forecast.json",            "content_type": "application/json", "size": 4096 },
    { "name": "external_signals.json",     "href": "/api/v1/forecasts/{id}/artifacts/external_signals.json",     "content_type": "application/json", "size": 2048 },
    { "name": "backtest_metrics.json",     "href": "/api/v1/forecasts/{id}/artifacts/backtest_metrics.json",     "content_type": "application/json", "size": 1280 },
    { "name": "backtest_trajectories.json","href": "/api/v1/forecasts/{id}/artifacts/backtest_trajectories.json","content_type": "application/json", "size": 8192 }
  ]
}
```

If `status` is `failed` or `canceled`, the response includes a `pipeline_error`
object with a `code` and a `detail` field.

### 2.5 Download artifacts

Use the `name` values from the artifacts array. Available at
`GET /api/v1/forecasts/{id}/artifacts/{name}`.

| File | When present | Contents |
|------|--------------|----------|
| `forecast.json` | Always | Point forecasts + quantile bands for each horizon month |
| `external_signals.json` | Always | Ranked external drivers with importance, direction, correlation |
| `backtest_metrics.json` | When `backtest: true` | Aggregated accuracy (MAPE, RMSE) over rolling 6m/12m/24m/60m windows |
| `backtest_trajectories.json` | When `backtest: true` | Per-fold actual vs forecast for the last 12 months |

```bash
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
  "https://api.sybilion.dev/api/v1/forecasts/$JOB_ID/artifacts/forecast.json"
```

### 2.6 `forecast.json` shape (IMPORTANT — this is what the calculator parses)

6-month horizon, one point shown:

```json
{
  "version": "1.1",
  "data": {
    "forecast_horizon": 6,
    "forecast_start": "2026-01-01",
    "forecast_end": "2026-06-01",
    "forecast_series": {
      "2026-01-01": {
        "forecast": 78.40,
        "quantile_forecast": { "0.1": 68.2, "0.5": 78.4, "0.9": 89.1 }
      },
      "2026-02-01": {
        "forecast": 79.15,
        "quantile_forecast": { "0.1": 68.8, "0.5": 79.2, "0.9": 89.9 }
      }
    }
  }
}
```

> **Note the structure:** keys are date strings; each point has a `forecast`
> (point estimate) and a `quantile_forecast` with keys `"0.1"` (low / p10),
> `"0.5"` (median / p50), `"0.9"` (high / p90). The calculator must read
> `data.forecast_series[date].quantile_forecast["0.5"]` for the median, not a
> field called `p50`.

### 2.7 Pricing

Billing only on `2xx`. Cost = base fee + a variable component that scales with
how long the job takes. A pre-charge hold is applied on successful submission; if
balance is insufficient, the operation is blocked.

---

## 3. Drivers (synchronous)

Drivers are external macroeconomic signals that Sybilion identifies as the most
relevant influences on a given time series. They quantify **which signals shaped
the projection and by how much.** They appear as attributions inside a forecast's
`external_signals.json`, and can also be requested on their own.

`POST /api/v1/drivers` returns a **ranked list of drivers with importance and
direction scores immediately — no polling.** Use it for quick driver
recommendations without running a full forecast.

Driver quality depends on:
- **`keywords`** — embed domain knowledge into driver selection (this is real
  technical work, not preprocessing; good keywords drive good results).
- **`recency_factor`** — shifts the news window used to augment the search.
- **`filters`** — narrow the candidate universe by region and category.

Pricing: billing only on `2xx`; cost scales with the number of result items
returned. A pre-charge hold assumes the maximum returnable items.

---

## 4. Other endpoints (reference only — not needed for MVP)

- **Alerts** (`POST /api/v1/alerts`, sync) — ranked list of macroeconomic events
  and shocks relevant to a time series, with trend direction, percentage change,
  and supporting news articles. Useful later for the "market event" angle.
- **Regions & categories** (`GET /api/v1/regions`, `GET /api/v1/categories`) —
  read-only catalogs of integer ids accepted by the `filters` object on
  Forecasts / Drivers / Alerts. Not billed.
- **Account & usage** (`GET /api/v1/me`, `/usage`, `/jobs`) — balance, credit
  grants, charge history, async job summaries. Read-only. Note: `balance` is the
  ledger total; `available` is lower while async jobs hold a reserve.

---

## 5. What this means for our build

- **Forecast = async + slow + costs money.** Call it rarely, cache the result.
  Block 4 (Sybilion + report agent) must save the first real `forecast.json` and
  `external_signals.json` to the `mock/` folder and develop against the cache.
- **Use Sybilion's Python SDK** for the forecast calls where possible (submit +
  poll + fetch artifacts); fall back to raw HTTP only if needed. Always wrap with
  a mock fallback so the demo never blocks on the network.
- **The calculator/report reads `quantile_forecast` keys `"0.1"/"0.5"/"0.9"`**,
  not `p10/p50/p90`. Parse accordingly, then expose them to the frontend as
  `low/forecast/high` per the result contract in `ARCHITECTURE.md` §5.6.
- **Drivers** come from `external_signals.json` (importance, direction,
  correlation). Surface them in the report's `drivers[]`, and where horizon-level
  importance is available, include `horizon` so the UI can show how importance
  shifts across months.
- **Backtest** (`backtest_metrics.json`: MAPE/RMSE) must be surfaced on the
  dashboard and feed `decision.confidence`. The jury explicitly rewards backtest
  discipline.
- **Time series must satisfy the 40/60/120 minimums** and use first-of-month
  keys within the past 12 months, or submission is rejected (422). The
  data-engineer (Block 2) targets the last 60 monthly observations.

