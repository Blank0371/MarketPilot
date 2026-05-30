# TASK — Implement the v2.0 decision model in `backend/report_agent.py`

You are a senior Python engineer. Your job is to rewrite `backend/report_agent.py`
so it implements the decision model specified in **`backend/MODEL.md`**. That spec
is the **source of truth** for every formula, table, constant, and threshold.
Read it fully before writing any code.

> **Read order, mandatory, before touching code:**
> 1. `backend/MODEL.md` — the model you are implementing (every number lives here)
> 2. `ARCHITECTURE.md` §5.6 — the exact output report contract you must produce
> 3. The current `backend/report_agent.py` — what you are replacing and what to keep
> 4. `backend/sybilion_client.py` — how the forecast bundle arrives (you call `get_forecast`)
> 5. `backend/translation_agent.py` — the `FeatherlessClient` pattern you will reuse for LLM calls

Do not invent anything that is not in `MODEL.md`. If `MODEL.md` and any other doc
disagree about how a number is computed, **`MODEL.md` wins** — and flag the
mismatch in a code comment, do not silently pick the other.

---

## 0. The one rule that defines this task

**The LLM classifies and explains; deterministic Python computes every number and
the verdict.** (`MODEL.md` §0, P2.) Concretely:

- An LLM **profiler** classifies the business onto axes → returns categories only.
- Deterministic code maps categories → coefficients (from the `MODEL.md` tables)
  and computes revenue, costs, profit, break-even, payback, indices, score, risk,
  and the `decision_label`.
- An LLM **phrases the reason** over the already-computed numbers — it may not
  change any number or the verdict, and a validator rejects any invented number.

If you ever find yourself letting the LLM output a number that flows into the
economics or the verdict, you are doing it wrong. Stop and re-read `MODEL.md` §0.

**Every hard-coded number you introduce must carry a `# see MODEL.md §X.Y`
comment** (`MODEL.md` §P4, and the §10 correspondence table is your checklist).

---

## 1. Scope — what to build

Implement, per `MODEL.md`, in `backend/report_agent.py`:

1. **Forecast-horizon contract (§2.1–§2.2).** Accept `forecast_horizon_months`
   (default 6, clamp to 1–12) through the public functions and pass it to
   `sybilion_client.get_forecast(...)` as the horizon / `soft_horizon`. Remove the
   hard-coded assumption that the horizon is always 6.

2. **Run modes `dev` / `prod` (§1.1, P6).** Read `MODEL_MODE` from the environment
   (default `prod`). Implement the fallback policy table in §1.1:
   - `dev`: on any failure (LLM unavailable, forecast unavailable, a step raises) →
     **raise an error**. No silent fallbacks.
   - `prod`: use the documented loud fallbacks (neutral profile, synthetic forecast
     via the client, deterministic reason template) **and** record each one that
     fired in a `runtime.fallbacks` list that ends up in the report.
   - The report gains a `runtime` block: `{"mode": <dev|prod>, "fallbacks": [...]}`
     (empty list when everything ran on real paths). See §5 below.

3. **STEP A — LLM profiler (§3).** New function that takes `descriptions` +
   `user_input` and returns the 8-axis category JSON in §3.2 / §3.3. Enforce the
   closed enums (§3.4): any value outside the list → the documented middle value.
   On unavailable LLM: `prod` → neutral profile + record fallback; `dev` → error.
   The profiler must NOT see history, forecast, or money.

4. **STEP B — parameter cascade + tables (§4, §5).** Implement the coefficient
   tables exactly as in §5.1–§5.6 (basket, margin, 5-level payback profile, the
   three-axis volatility σ with the [0.10, 0.35] corridor, fixed-cost components).
   Implement the resolution cascade (§5.7): each parameter resolves to
   `{value, source, confidence, corridor}` with priority user → derived → default
   (→ llm_adjusted inside the corridor). **Sparse user input is NOT penalized**
   (§5.7, §6.5).

5. **STEP C — indices (§6).** Implement `SI` (§6.1), `CI` (§6.2), `ROI` (§6.3),
   `PB` (§6.4), and the composite `CONF` (§6.5). For `CONF`: three active
   components with weights 0.50/0.25/0.25; `c_data = clip(L/60, 0, 1)`;
   `c_assumptions` fixed at 1.0 (does not penalize sparse input); `c_band`
   computed **volume-weighted** as described in §6.5.

6. **STEP D — economics core (§7).** Replace `BASKETS_PER_INDEX_POINT` with the
   traceable `scale` cascade (§7.1). Implement revenue (§7.2), profit and the
   **analytical** break-even via the normal CDF (§7.3, replacing the 20k-sample
   Monte-Carlo), downside/upside via `Z_P90`, and the two-way investment estimate
   with `divergence` (§7.4).

7. **STEP E — multi-dimensional decision (§8).** Implement `score` (4 components,
   §8.2), the `decision_label` with profile-relative payback thresholds and the
   hard CONF/MAPE overrides (§8.3), and `risk_level` (4 components, §8.4). The
   verdict must depend on break-even AND payback-vs-profile AND confidence AND
   risk — not break-even alone.

8. **STEP F — LLM reason over finished numbers (§9).** Pass ONLY the computed
   numbers/categories (the §9.1 shape). Enforce the strict prompt (§9.2) and the
   output validation (§9.3): reject any number not present in the input (with a
   rounding tolerance) and any verdict mismatch. On failure: `prod` → deterministic
   template + record fallback; `dev` → error.

---

## 2. Public interface — keep it importable and orchestrator-friendly

The orchestrator (`backend/main.py`) and the what-if path depend on these. Keep
these names and shapes (extend signatures with the horizon; do not rename):

```python
def build_report(
    timeseries: dict[str, float],
    metadata: dict | None = None,
    user_input: str = "",
    descriptions: list[str] | None = None,
    *,
    forecast_horizon_months: int = 6,
    forecast_bundle: dict | None = None,
) -> dict: ...

def prepare_context(...) -> ReportContext: ...        # fetch forecast once, bundle inputs
def recompute(context: ReportContext, overrides: dict | None) -> dict: ...  # what-if, no Sybilion call
```

- `recompute` must reuse the cached forecast in the context (no new Sybilion call)
  and re-run economics → decision → reason. This powers `/report/recompute`.
- `build_report` returns the full report dict matching `ARCHITECTURE.md` §5.6
  **plus** the new `runtime` block.

Keep the HTTP layer (`/report/build`, `/report/recompute`, `/health`) working.
Add `forecast_horizon_months` to the request models (optional, default 6).

---

## 3. Output contract — produce exactly this

Match `ARCHITECTURE.md` §5.6 field-for-field, and add `runtime`:

```json
{
  "decision": { "label": "...", "score": 0, "risk_level": "...", "confidence": 0.0, "summary": "..." },
  "expected_revenue": {
    "expected_monthly_revenue_eur": 0, "expected_monthly_costs_eur": 0, "expected_monthly_profit_eur": 0,
    "downside_monthly_profit_eur": 0, "upside_monthly_profit_eur": 0,
    "break_even_probability": 0.0, "payback_months": 0
  },
  "investment_cost": { "estimated_initial_investment_eur": 0, "breakdown": [ { "category": "...", "amount": 0 } ] },
  "graphs": { "demand_forecast": [ ... ], "historical_series": [ ... ] },
  "drivers": [ { "name": "...", "importance": 0.0, "direction": "...", "horizon": 1 } ],
  "backtest": { "mape": 0.0, "rmse": 0.0, "quality": "..." },
  "reason": { "main_reason": "...", "positive_factors": [], "negative_factors": [], "recommended_actions": [] },
  "runtime": { "mode": "prod", "fallbacks": [] }
}
```

- `decision.label` ∈ **Launch · Adapt concept · Delay · Do not launch**.
- `investment_cost.estimated_initial_investment_eur` MUST equal the sum of
  `breakdown[].amount` (keep this invariant — a test checks it).
- `graphs.*` points carry `historical`, `forecast`, `low`, `high` (history points
  have `forecast/low/high = null`; forecast points have `historical = null`).
- Validate the final shape with Pydantic models before returning (keep the
  existing `_Report` pattern; extend it with `runtime`).

---

## 4. Tests — DO THIS CAREFULLY (do not skip, do not silently delete)

The existing `tests/test_report_agent.py` is pinned to the **old** model and will
not all pass against v2.0. You must handle this explicitly and honestly:

1. **Do NOT delete tests to make the suite green.** That hides regressions.
2. Update `tests/test_report_agent.py` to the v2.0 model, preserving the *intent*
   of each test:
   - **Contract-shape test** → keep, and extend it to assert the new `runtime`
     block and that `investment_cost` sums to its breakdown.
   - **`test_baseline_is_adapt_concept`** → keep the *idea* (the ice-cream show
     case should read as a non-trivial verdict). Per `MODEL.md` §7.3, the
     analytical break-even must land around **0.55–0.60** on the demo data so the
     baseline stays **"Adapt concept."** If your implementation shifts it, first
     re-check your math against §7.3; only adjust the test if the spec-faithful
     result genuinely differs, and document why in a comment.
   - **`test_high_rent_lowers_profit_and_flips_verdict`** → keep: raising rent must
     lower profit and break-even and move the label toward Delay/Do not launch.
   - **`test_recompute_premium_basket_improves_verdict`** → keep the direction
     (higher basket → better verdict). The exact target label may change under
     v2.0; assert the *improvement*, not necessarily exactly "Launch", unless the
     spec-faithful result is "Launch".
   - **`test_bad_backtest_lowers_confidence`** → replace `confidence_from_backtest`
     with the new `CONF`: higher MAPE → lower `CONF`. Keep the intent.
   - **`test_break_even_uses_the_band`** → keep: downside < expected < upside.
   - **Tests referencing the retired subprocess codegen / `_validate_executed` /
     `_economics_inproc` / `REPORT_DISABLE_CODEGEN`** → these target the old
     two-path economics that v2.0 removes (`MODEL.md` §11). Replace them with a
     test that the deterministic economics are **reproducible** (same inputs →
     same numbers) and that break-even is computed analytically (no RNG seed
     dependence).
3. Add **2–4 new small tests** for v2.0 behavior:
   - the profiler enum-guard returns a valid profile on garbage LLM output (and the
     neutral-profile fallback in `prod`);
   - `forecast_horizon_months` is honored (e.g. 3 vs 6 changes how many forecast
     points drive the horizon average) and clamped to 1–12;
   - a low-`CONF` or high-MAPE input cannot produce "Launch" (the §8.3 override);
   - `runtime.fallbacks` is non-empty when a fallback path is exercised in `prod`.
4. Run `REPORT`-independent: set the model into a deterministic state for tests
   (no live LLM, no live Sybilion) using the existing offline patterns
   (`get_forecast(use_live=False)`, no `FEATHERLESS_API_KEY`). In tests, default to
   `prod` mode unless a test specifically checks `dev` error-raising.
5. The suite must end **green** after your changes:
   `pytest tests/test_report_agent.py -v`.

If any test cannot be made to pass without violating `MODEL.md`, leave it failing
with a clear `# TODO(model): ...` comment explaining the conflict — do not delete
it and do not weaken the model to satisfy a stale test.

---

## 5. Fallbacks, LLM calls, and resilience

- Reuse the **`FeatherlessClient`** pattern from `translation_agent.py` for both
  the profiler and the reason LLM (strict-JSON prompting, one retry with a
  stricter prompt). Do not add a new HTTP client.
- The forecast comes from `sybilion_client.get_forecast(timeseries, metadata,
  forecast_horizon_months=...)`. That client already returns `source` ∈
  `live|cache|mock`. In `prod`, if the source is not `live`/`cache` (i.e. a
  synthetic mock was generated) record `"sybilion_unavailable->synthetic_forecast"`
  in `runtime.fallbacks`. In `dev`, if a live forecast was required and not
  obtained, raise.
- Never return a raw 500 from the HTTP layer; return a structured error (keep the
  existing try/except pattern), except that in `dev` an internal error should
  surface clearly rather than be masked.
- All economics must be **deterministic and reproducible**: no RNG, no seeds
  (the analytical break-even in §7.3 removes the Monte-Carlo). Two identical
  inputs must yield byte-identical numbers.

---

## 6. Engineering standards

- Senior-level, clean, readable Python. Small single-purpose functions mirroring
  the `MODEL.md` steps (profiler / parameterize / indices / economics / decision /
  reason). Type hints throughout.
- Keep the module importable without side effects; keep the standalone
  `if __name__ == "__main__"` demo working (it should print a §5.6 report for the
  ice-cream series).
- Short comments where logic is non-obvious; a `# see MODEL.md §X.Y` next to every
  spec-derived constant.
- Do not over-engineer. Implement exactly what `MODEL.md` specifies — no extra
  features, no speculative configuration.
- Write directly into `backend/report_agent.py` (and `tests/test_report_agent.py`).
  Do not create parallel/scratch copies.

---

## 7. Definition of done

- [ ] `backend/report_agent.py` implements §§1–9 of `MODEL.md` (profiler →
      parameter cascade → indices → economics → multi-dimensional decision →
      validated LLM reason).
- [ ] `BASKETS_PER_INDEX_POINT` is gone; `scale` cascade (§7.1) is in.
- [ ] Monte-Carlo is gone; break-even is analytical (§7.3), deterministic, no seed.
- [ ] `forecast_horizon_months` flows from the public API into `sybilion_client`.
- [ ] `MODEL_MODE` controls fallbacks per §1.1; the report carries `runtime`.
- [ ] Output matches `ARCHITECTURE.md` §5.6 + `runtime`, Pydantic-validated;
      investment sums to its breakdown.
- [ ] Every spec-derived constant has a `# see MODEL.md §X.Y` comment and appears
      in the §10 correspondence table.
- [ ] `pytest tests/test_report_agent.py -v` is green; tests were *migrated*, not
      deleted; new v2.0 tests added.
- [ ] `python -m backend.report_agent` prints a valid §5.6 report for the demo.

When done, summarize: which `MODEL.md` sections you implemented, which old tests
you migrated (and how), which new tests you added, and any place where you had to
flag a spec/test/code conflict instead of resolving it.
