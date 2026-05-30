# BLOCK4.md — Sybilion + Report Agent (Master Prompt for Claude Code)

> **Before you start, read in this order:** `CLAUDE.md` → `ARCHITECTURE.md` →
> `SYBILION_DOC.md` → `FLOW_AND_AGENTS.md` → this file. Then begin.
>
> **Source of truth:** `FLOW_AND_AGENTS.md` is canonical (your role is in §4.3;
> the result contract is `ARCHITECTURE.md` §5.6). This block file is
> authoritative for your work. Ignore older docs that use a "wine store" — the
> show case is an **ice cream shop in Vienna**.
>
> **Product:** MarketPilot — *Navigate uncertainty before you launch.*
> **Stack:** backend is **Python**. (The frontend that consumes your JSON is
> **TypeScript + React** — produce JSON that matches the result contract exactly
> so it renders cleanly.)

---

## 0. Who you are

You are Claude, acting as a **senior backend engineer with 20 years of
experience.** You build the most substantive part of this system: the layer that
turns a probabilistic forecast into a transparent, reproducible decision. You
apply best practices by default, keep deterministic logic deterministic, and
never let the demo crash. You don't over-engineer a hackathon prototype.

---

## 1. Your role

You build the **Sybilion + report agent** in four parts:

1. **Sybilion client** — transform the Data-Engineer time series into the
   Sybilion request, run the forecast via **Sybilion's Python SDK**, fetch the
   artifacts. Mock fallback built in.
2. **Report computation** — the LLM decides which statistical tests/derivations
   are needed and **writes and executes its own Python** to compute the figures.
   The actual numbers come from **executed deterministic Python**, not from the
   model guessing.
3. **Decision logic** — a deterministic verdict (Launch / Adapt concept / Delay /
   Do not launch) derived from the computed figures + backtest.
4. **Assembler** — package everything into the final report JSON for the
   frontend.

Files: `backend/sybilion_client.py`, `backend/report_agent.py`. Work directly in
`main` at the real paths.

---

## 2. Inputs you receive

From the pipeline (via the orchestrator): the **Data-Engineer response** (time
series + metadata, `FLOW_AND_AGENTS.md` §4.2), plus the original **userInput** and
the confirmed **descriptions** for context.

---

## 3. Part 1 — Sybilion client

1. **Build the Sybilion request** from the Data-Engineer response:
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
2. **Submit via the Sybilion Python SDK** (preferred). Poll until the job is
   `completed`, then fetch the artifacts: `forecast.json` (point + quantile
   bands `"0.1"/"0.5"/"0.9"`), `external_signals.json` (drivers: importance,
   direction, correlation), and `backtest_metrics.json` (MAPE/RMSE). See
   `SYBILION_DOC.md`.
3. **Cache the first real response** to `mock/forecast.json` (and the signals /
   backtest). Develop against the cache afterward — the forecast is async, slow,
   and costs money.
4. **Fallback:** on timeout / failure / missing key, load the cached/mock
   artifacts and tag the result `source: "cache"`. The demo must never block on
   the network.

Expose `get_forecast(timeseries, metadata) -> {forecast, drivers, backtest}`
with the fallback inside.

---

## 4. Part 2 — Report computation (LLM writes & executes Python)

Per the source of truth: the LLM uses the prediction to **decide which
statistical work is needed**, then **creates its own Python scripts and executes
them** to produce the report figures.

- Parse the forecast: read `data.forecast_series[date].quantile_forecast` keys
  `"0.1"` (downside), `"0.5"` (base), `"0.9"` (upside) for each month.
- Compute the core economics deterministically (executed Python):
  - `expected_monthly_revenue = base_demand × average_basket_price`
  - `gross_profit = expected_monthly_revenue × margin`
  - `expected_monthly_costs = rent + staff_costs + other_fixed_costs`
  - `expected_monthly_profit = gross_profit − expected_monthly_costs`
  - downside/upside profit from the `0.1` / `0.9` demand paths.
- **Break-even probability:** estimate the probability that monthly profit is
  positive across the downside/base/upside band (e.g. sample the band and measure
  the share of profitable scenarios). This uses the uncertainty rather than
  hiding it — the jury rewards that.
- **Investment cost:** estimate the initial investment and a breakdown
  (inventory, setup, marketing, legal, cash buffer).
- **Graphs:** assemble the series the frontend plots — historical points and the
  forecast continuation with `low`/`high` band, in the result-contract shape.

> Guardrail: the LLM orchestrates and writes the Python, but **the numbers and
> the verdict must be reproducible from the executed calculation.** Do not let the
> model invent figures or flip the decision. This is what keeps us out of the
> "LLM-wrapper" failure mode the track forbids. Execute scripts in a safe,
> sandboxed way; validate outputs before trusting them; on failure, fall back to
> a fixed deterministic calculation.

---

## 5. Part 3 — Decision logic (deterministic)

Derive the verdict from the computed figures + backtest. Reasonable default rules
(tune so the ice cream default lands sensibly):

- `break_even_probability ≥ 0.75` **and** `expected_monthly_profit > 0` → **Launch**
- else `≥ 0.55` → **Adapt concept**
- else `≥ 0.40` → **Delay**
- else → **Do not launch**

Also compute:
- `score` (1–100 quality indication),
- `risk_level` (Low / Medium / High) from band width + competition,
- `confidence` — **tie this to backtest quality**: a weak backtest (high MAPE)
  lowers confidence; a strong one raises it. Surface the backtest on the
  dashboard too. The verdict is computed, not LLM-decided.

---

## 6. Part 4 — Assembler

Produce the final report JSON exactly as `ARCHITECTURE.md` §5.6:
`decision`, `expected_revenue`, `investment_cost`, `graphs`, `drivers`,
`backtest`, `reason`. Map `external_signals.json` into `drivers[]` (name,
importance, direction, and `horizon` if available so the UI can show how
importance shifts across the horizon).

The **`reason`** block (main reason, positive/negative factors, recommended
actions) may be phrased by the LLM **from the already-computed result** — explain,
don't decide or invent numbers.

Expose `build_report(timeseries, metadata, user_input, descriptions) -> dict`.

---

## 7. Adaptivity hook (important)

The jury changes an assumption live. Support a **fast recompute that reuses the
cached forecast**: given the existing forecast + new assumption overrides (rent,
basket price, margin), recompute economics, break-even, and the verdict **without
calling Sybilion again**. Expose `recompute(report_context, overrides) -> report`
and (with the orchestrator) a fast endpoint the frontend can hit. This makes the
"adapts mid-run" demo instant and cheap.

---

## 8. Requirements & definition of done

- Sybilion forecast runs via the **Python SDK** with submit → poll → fetch, and a
  **mock/cache fallback**; first real response cached to `mock/`.
- Forecast parsed from `quantile_forecast` `"0.1"/"0.5"/"0.9"`; economics computed
  by **executed deterministic Python**; break-even from the band.
- **Deterministic verdict** by rules; `confidence` tied to **backtest**; backtest
  surfaced in the output.
- Final JSON matches `ARCHITECTURE.md` §5.6 exactly (the React frontend depends on
  it); drivers include `horizon` when available.
- **Fast `recompute()`** reuses the cached forecast for live what-ifs.
- LLM is used to orchestrate/write Python and to phrase the `reason` — never to
  invent the numbers or the decision.
- 2–3 tests in `tests/test_report_agent.py` (e.g. high rent lowers profit and can
  flip the verdict; bad backtest lowers confidence; recompute changes the
  result). Code at `backend/sybilion_client.py` and `backend/report_agent.py`.
- If anything conflicts with another doc, follow `FLOW_AND_AGENTS.md`.
