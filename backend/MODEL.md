# MODEL.md — MarketPilot Decision Model Specification

**Version:** 2.0
**Block:** 4 (report_agent)
**Purpose:** Formally describe the decision model so that **every number in the code has a line in this document**. No magic constant without justification. This is the document that defends the model to the jury on the criterion *"accuracy, not generated bullshit."*

> This is the English companion to the model specification. It is the
> authoritative description of how `report_agent.py` turns a Sybilion forecast
> into a launch decision.

---

## 0. Model principles (read first)

These principles are the frame. Breaking them turns the model back into a pile of magic numbers.

**P1. There is no ground truth.** We forecast the revenue of a business that does not exist yet. We cannot verify "is €18,500/mo correct." Therefore "accuracy" means three measurable properties:
- **internal consistency** — the numbers do not contradict each other;
- **forecast calibration** — how much the Sybilion forecast can be trusted (via MAPE);
- **traceability** — every coefficient is derived from an input or from a justified table, never from thin air.

**P2. Separation of LLM and code roles.** This is the central principle of the whole design:
- **The LLM classifies and parameterizes** — it determines business categories, picks a profile, extracts numbers from text. The LLM is strong at classification.
- **Code computes** — all money, probabilities, and the verdict are computed by deterministic formulas.
- **The LLM explains** — it phrases already-computed numbers in words.
- **The LLM NEVER invents a result and NEVER decides the verdict.**

**P3. Every coefficient is `(base value from a table, corridor, source)`.** The LLM may move a coefficient inside the corridor with justification. It may not leave the corridor. The source is always recorded: `user` / `derived` / `default` / `llm_adjusted`.

**P4. Every number in the code references a section of this document.** In code, a comment `# see MODEL.md §X.Y`. This rule is checked at review. No reference → the number has no right to exist.

**P5. Classification by axes, not by types.** Because we support "any offline retail," we do NOT keep a list of types (ice cream, kebab, gas station…). Instead, a set of **continuous/categorical axes** (capital intensity, perishability, seasonality…) onto which any business projects. The user's business type → the LLM projects it onto the axes.

**P6. Two run modes: `dev` and `prod`.** Behavior on failure (LLM not responding, forecast unavailable, model crashes) depends on the mode:
- **`dev` — no fallbacks.** If the LLM does not respond, there is no forecast, or any step fails — **an error is raised**. Goal: during development we want to see real failures, not silently run on stubs and believe everything is fine. A silent fallback in dev masks bugs.
- **`prod` — fallbacks enabled, but loud.** The synthetic forecast fallback (`sybilion_client`), the neutral profile on an unavailable LLM (§3.4), etc. are used. **Every fallback must explicitly report what happened:** the response carries a flag/message such as "LLM did not answer → neutral profile" or "Sybilion unavailable → synthetic forecast." The user and the jury always see that the result is partly on a fallback, not on real data.

The mode is set by an environment variable (e.g. `MODEL_MODE=dev|prod`). Everywhere below where a fallback is described, it applies **only in `prod`**; in `dev` the same case is an error. This is a cross-cutting rule; it is not repeated in every section.

---

## 1. Model flow overview

```
                  INPUT
   ┌──────────────────────────────────────┐
   │ • timeseries (history, ~60 mo)        │  ← from Data Engineer
   │ • forecast_bundle (forecast+drivers+  │  ← from sybilion_client
   │   backtest with MAPE/RMSE)            │
   │ • descriptions (free text)            │  ← from Translation Agent
   │ • user_input (what the user typed)    │
   │ • forecast_horizon_months (contract)  │  ← request parameter (§2.2)
   └──────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP A. PROFILER  (LLM)               │  §3
   │ classifies the business onto axes →   │
   │ returns CATEGORIES, not numbers       │
   └──────────────────────────────────────┘
                     │  business_profile
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP B. PARAMETERIZATION (code+tables)│  §4, §5
   │ categories → coefficients from tables │
   │ + assumption cascade (user/derived/   │
   │   default)                            │
   └──────────────────────────────────────┘
                     │  resolved_parameters
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP C. INDICES (code)                │  §6
   │ seasonality, capital intensity,       │
   │ payback, ROI, confidence — formulas   │
   └──────────────────────────────────────┘
                     │  indices
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP D. ECONOMICS CORE (code)         │  §7
   │ revenue → costs → profit →            │
   │ break-even → payback                  │
   └──────────────────────────────────────┘
                     │  economics
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP E. DECISION (code)               │  §8
   │ multi-dimensional decision_label,     │
   │ score, risk_level — from the indices  │
   └──────────────────────────────────────┘
                     │  decision
                     ▼
   ┌──────────────────────────────────────┐
   │ STEP F. EXPLANATION (LLM)             │  §9
   │ phrases the finished numbers in words │
   │ strict prompt, never changes numbers  │
   └──────────────────────────────────────┘
                     │
                     ▼
              REPORT CONTRACT (§5.6 of ARCHITECTURE.md)
```

Compared to the old code: steps A, B, C are new (previously there was `BASKETS_PER_INDEX_POINT` and fixed `Assumptions`). Step D is the existing `compute_economics` with a new source of parameters. Step E expands the one-dimensional `_decision_label` into a multi-dimensional one. Step F is what `_maybe_llm_reason` already partly does, but broader.

### 1.1 `dev` / `prod` modes and fallback policy

Implements P6. The same code; behavior on failure is decided by the mode (`MODEL_MODE=dev|prod`). This is a cross-cutting table — other sections reference it rather than repeating it.

| Failure point | `dev` (no fallbacks) | `prod` (fallback + explicit message) |
|---|---|---|
| LLM profiler did not answer (§3.4) | **error** | neutral profile + message "profiler unavailable → neutral profile" |
| Sybilion unavailable / timeout | **error** | synthetic forecast from history (`sybilion_client`) + message "Sybilion unavailable → synthetic forecast" |
| LLM explanation did not answer (§9) | **error** | deterministic reason template + message "LLM explanation unavailable → template" |
| Any computation step crashed | **error (with traceback)** | clean error response, never a raw 500 |

**Why this design:**
- **`dev`** — during development a silent fallback is dangerous: it masks a bug (you think the real path is running, but it is actually a stub). So in dev everything that should work must either work or fail loudly.
- **`prod`** — on stage / in production it must not crash, so fallbacks are on. But **every fallback is loud**: the response has a field (e.g. `runtime.fallbacks: ["sybilion→synthetic"]`) that the frontend shows and the jury sees honestly — "this result is partly on a fallback, not on real data." No silent substitutions even in prod.

**Fallback message contract (prod):** the report adds an optional block:
```json
"runtime": {
  "mode": "prod",
  "fallbacks": ["sybilion_unavailable->synthetic_forecast"]
}
```
An empty `fallbacks` means everything was computed on real paths.

---

## 2. Glossary of quantities

So the formulas below read unambiguously.

| Symbol | Meaning | Source |
|---|---|---|
| `H` | forecast horizon, months | request contract, §2.1–§2.2 |
| `L` | history length, months | `len(timeseries)` |
| `idx[t]` | forecast demand index for month t | forecast_bundle |
| `idx_low[t]`, `idx_high[t]` | 10th and 90th percentile of the forecast | forecast_bundle |
| `mape` | Sybilion backtest error | forecast_bundle.backtest |
| `s[m]` | seasonal multiplier of month m (m=1..12) | computed, §6.1 |
| `scale` | bridge "index → transactions/month" | §7.1 |
| `price` | average basket, € | cascade §5 |
| `margin` | gross margin, fraction [0,1] | cascade §5 |
| `fixed` | monthly fixed costs, € | cascade §5 |
| `I` | initial investment, € | §7.4 |

### 2.1 Fixed structural constants

These are **not** "magic" — they are structural parameters of the problem, not tuned. Each is justified.

| Constant | Value | Justification |
|---|---|---|
| `H` (horizon) | **from the request contract** (default 6) | **The number of forecast months is a request parameter, not a hard-coded constant.** It arrives with the input (see §2.2). Sybilion `soft_horizon` is set to the same value. Default 6 if the request omits it. Beyond ~6 months the forecast loses accuracy quickly, so a reasonable ceiling is ~12. |
| `L_min` (min history) | 24 mo | Need at least 2 full yearly cycles to estimate seasonality (§6.1). Less → seasonality unreliable, confidence penalty (§6.5). |
| `L_full` (history for full confidence) | 60 mo (5 years) | At 5 years of history `c_data` = 1.0 (§6.5). Five years cover several seasonal cycles and smooth one-off shocks — enough for a confident seasonality and trend estimate. |
| `MONTHS_PER_YEAR` | 12 | Calendar. |
| `Z_P90` | 1.2816 | 90th percentile of the standard normal distribution. Used in the synthetic fallback (sybilion_client) and in the downside/upside band (§7.3). A pure mathematical constant. |

### 2.2 Forecast horizon contract

The horizon `H` (how many months ahead we predict) **arrives in the request**, not hard-coded. This allows changing forecast depth without touching the model and keeps the Sybilion request aligned with the economics core.

```
analyze request:
{
  "userInput": "...",
  "forecast_horizon_months": 6      // ← contract; default 6, range 1..12
}
```

Rules:
- the value is passed to `sybilion_client` as `soft_horizon` (currently hard-coded `FORECAST_HORIZON = 6` — becomes a parameter);
- the same value is used in §7.2 (averaging revenue over the horizon) and in the seasonality cross-check;
- if the request omits it → default 6;
- a value outside [1, 12] → clamped into that range (in `dev` — an error, per P6).

---

## 3. STEP A — Profiler (LLM)

### 3.1 What it does

The LLM receives `descriptions` + `user_input` + metadata and **classifies the business onto axes**. It returns strictly structured JSON with categories. **The LLM emits no numbers here** — only labels from closed lists.

### 3.2 Classification axes

This is the core of supporting "any offline retail." Any business projects onto these axes.

| Axis | Possible values | What it drives in the model |
|---|---|---|
| `capital_intensity` | `very_low` / `low` / `medium` / `high` / `very_high` | initial investment, payback profile (§5.3, §8.3) |
| `perishability` | `none` / `low` / `high` | demand volatility, risk (ice cream melts — high; auto parts — none) |
| `seasonality_expectation` | `flat` / `moderate` / `strong` | prior expectation of seasonality (cross-checked with computed §6.1) |
| `demand_breadth` | `mass` / `mixed` / `niche` | demand volatility, forecast band width (§5.4) |
| `margin_class` | `low` / `medium` / `high` | base margin (§5.2) |
| `ticket_class` | `low` / `medium` / `high` | base average basket (§5.1) |
| `purchase_frequency` | `daily` / `periodic` / `rare` | series predictability → confidence (§6.5); frequent purchases = smoother series = higher confidence |
| `external_shock_sensitivity` | `low` / `medium` / `high` | volatility and risk (§5.4, §8.4); sensitivity to irregular external factors (day's weather, fashion, events) |

**About the two new axes (v2.0):**
- **`purchase_frequency`** — how often a single customer returns. Does not duplicate `demand_breadth` (that is about audience width, this is about a single customer's rhythm: mattresses are mass but bought once in years). A direct predictor of predictability: `daily` → many transactions → smooth series → low MAPE → higher `c_data` confidence; `rare` → choppy demand → lower.
- **`external_shock_sensitivity`** — dependence on irregular factors. Does not duplicate `seasonality` (that is the *regular* predictable cycle) or `perishability` (that is the product itself). Ice cream is strongly seasonal (predictable) AND weather-dependent (noisy) — two distinct axes. High sensitivity → wider band, higher risk.

These two axes are the main tool for the "pick a domain where the forecast is accurate" strategy: `daily` + `low shock` = candidates with low MAPE (groceries, pharmacy, highway gas station).

### 3.2.1 Capital intensity at 5 levels — justification for the split

`capital_intensity` is split to 5 levels (other axes kept at 3) because the spread of startup investment in offline retail is enormous — from a coffee stand (~15k) to a gas station (~300k+), a 20×+ range. Here each extra level yields a **noticeably different** payback profile (§5.3) and is justifiable by its own line. Other axes were NOT split to 5 (the P5 test: you cannot justify each gradation separately — `low` vs `very_low` margin are indistinguishable, which would be fake precision).

### 3.3 Profiler output format

```json
{
  "capital_intensity": "very_high",
  "perishability": "none",
  "seasonality_expectation": "moderate",
  "demand_breadth": "mass",
  "margin_class": "low",
  "ticket_class": "high",
  "purchase_frequency": "periodic",
  "external_shock_sensitivity": "low",
  "reasoning": "Gas station: very high upfront equipment investment, fuel does not perish, demand is stable and barely fashion/weather-driven, refueling is periodic...",
  "confidence": 0.8
}
```

`reasoning` — for audit and for step F, not used in computations. `confidence` — the LLM's self-assessment of its own classification; **in v2.0 it does NOT enter `CONF`** (see §6.5); it is used only for the dashboard/logs.

### 3.4 Hallucination control at step A

- All fields **strictly from closed lists** (enum). A value outside the list → rejected, the middle is used (`medium`/`moderate`/`mixed`; for `capital_intensity` the middle is `medium`; for `purchase_frequency` it is `periodic`; for `external_shock_sensitivity` it is `medium`).
- **If the LLM is unavailable (behavior by mode, P6):**
  - **`prod`:** the whole profile = neutral middle values on all axes, the model keeps working, **and the response adds an explicit message** "profiler unavailable → neutral profile is used."
  - **`dev`:** an error is raised (no silent neutral profiles — we want to see that the LLM did not answer).
- The LLM **does not see** the history, the forecast, or the money — only the text description of the business. It physically cannot "tune" the classification toward a desired result, because it does not know the result.

---

## 4. STEP B — Parameterization: from categories to coefficients

The tables below implement principle P3: `(base value, corridor, source)`. The LLM at step A picked a category; code takes the base value and corridor from the table; if needed, the LLM on a separate narrow call moves inside the corridor with justification.

All numbers below are **our expert estimates, honestly marked as assumptions** (a table + LLM mix). Each comes with a justification. These are order-of-magnitude assumptions, not truth — and that is exactly how they are presented to the jury.

---

## 5. Coefficient reference tables (defaults)

### 5.1 Average basket by `ticket_class`

| `ticket_class` | Base, € | Corridor, € | Justification |
|---|---|---|---|
| `low` | 6 | 3–10 | Impulse purchase: ice cream, coffee, pastry. |
| `medium` | 25 | 10–60 | Mid retail ticket: books, cosmetics, fast-food lunch. |
| `high` | 60 | 40–150 | Gas station (full tank), electronics, small furniture. |

**Source:** expert estimate over typical offline categories. **Priority:** if the user gave the basket explicitly → their value overrides the table (cascade §5.7).

### 5.2 Gross margin by `margin_class`

| `margin_class` | Base | Corridor | Justification |
|---|---|---|---|
| `low` | 0.20 | 0.10–0.30 | Fuel, electronics — sold near cost, earn on turnover. |
| `medium` | 0.50 | 0.35–0.65 | Most general retail. |
| `high` | 0.70 | 0.60–0.85 | Food service, coffee, ice cream — high markup on inputs. |

**Source:** expert estimate of typical retail gross margins. **Note:** this is gross margin (after COGS, before fixed costs), not net.

### 5.3 Payback profile by `capital_intensity`

Defines what payback is considered "normal" for this business. This is the key to the adaptive decision_label thresholds (§8.3) — it solves the "a gas station pays back slower than a kebab shop, but that is normal" problem.

| `capital_intensity` | Base investment, € | Normal payback, mo | Tolerable payback, mo | Justification |
|---|---|---|---|---|
| `very_low` | 12,000 | 8 | 15 | Micro-start: coffee window, stand, minimal equipment. Very fast return expected. |
| `low` | 25,000 | 12 | 24 | Light start (small point): small investment, fast return expected. |
| `medium` | 80,000 | 24 | 42 | Café, shop: medium investment in premises and equipment. |
| `high` | 250,000 | 42 | 72 | Small-format gas station, production: heavy capex, long return — industry norm. |
| `very_high` | 600,000 | 60 | 96 | Large gas station/production/big format: very heavy capital, 5–8 year payback — an industry norm, not a reason to "do not launch." |

**Source:** expert estimate. **How it is used:** the business payback (§6.4) is compared against the "normal/tolerable" threshold of ITS profile, not against a universal number. A `very_high` gas station with payback 70 mo → within tolerable (96) → not penalized. A `low` kebab shop with payback 70 mo → far above tolerable (24) → hard penalty. This is the thresholds adapting to business type.

### 5.4 Demand volatility by `demand_breadth` × `perishability` × `external_shock_sensitivity`

Defines how wide the forecast band is and how high the risk is. Built from three axes.

Base relative volatility (σ as a fraction of mean demand):

| `demand_breadth` | σ contribution | Justification |
|---|---|---|
| `mass` | 0.10 | Mass demand averaged over many buyers → stable. |
| `mixed` | 0.18 | — |
| `niche` | 0.28 | Narrow demand sensitive to fashion/events → jumpy. |

Perishability add-on:

| `perishability` | σ add-on | Justification |
|---|---|---|
| `none` | 0.00 | Non-perishable goods can be held → no clearance pressure. |
| `low` | 0.03 | — |
| `high` | 0.06 | Perishables (ice cream, fresh food) → losses on demand dips, higher effective volatility. |

External-shock add-on (new axis v2.0):

| `external_shock_sensitivity` | σ add-on | Justification |
|---|---|---|
| `low` | 0.00 | Stable demand (groceries, pharmacy) → irregular factors barely matter. |
| `medium` | 0.04 | Moderate dependence (café with a terrace — weather). |
| `high` | 0.08 | Strong dependence on fashion/events/day's weather → large irregular spread around the forecast. |

**Final σ** = (demand_breadth contribution) + (perishability add-on) + (external_shock_sensitivity add-on), then clamped to the corridor **[0.10, 0.35]**.

**Corridor justification:** a synthetic/forecast series systematically understates real noise; the floor 0.10 keeps the model from being naively confident; the ceiling 0.35 (raised from 0.30 in v2.0, since a third add-on was added and the maximum sum grew) keeps the band from becoming meaninglessly wide. Explainable to the jury as "protection against false confidence."

### 5.5 Axis → effect summary

| Axis | §5.1 basket | §5.2 margin | §5.3 payback | §5.4 σ/risk | §6.5 confidence |
|---|---|---|---|---|---|
| `ticket_class` | ✔ | | | | |
| `margin_class` | | ✔ | | | |
| `capital_intensity` | | | ✔ | | |
| `demand_breadth` | | | | ✔ | |
| `perishability` | | | | ✔ | |
| `external_shock_sensitivity` | | | | ✔ | |
| `seasonality_expectation` | | | | | ✔ (cross-check with §6.1) |
| `purchase_frequency` | | | | | ✔ (series predictability) |

### 5.6 Fixed costs (`fixed`)

Decomposed into components, each a cascade (§5.7):

| Component | Base, €/mo | Source of base |
|---|---|---|
| Rent | 6,000 | derived from location (area × district rate) if available; else default |
| Staff | 9,000 | derived from expected headcount by type; else default |
| Other fixed | 2,400 | default (utilities, insurance, software) |

`fixed = rent + staff + other`. (Keeps the `Assumptions.fixed_costs_eur` logic, but each component now has a source instead of being hard-coded.)

### 5.7 Assumption resolution cascade (the P3 mechanism)

For **each** parameter (basket, margin, rent, staff, other, investment) the same cascade applies:

```
1. Present in user_input?     → take it,  source = "user",    confidence = 1.0
2. Derivable from data?       → compute,  source = "derived", confidence = 0.7
3. Otherwise                   → table base, source = "default", confidence = 0.5
   3a. LLM moved within corridor? → source = "llm_adjusted", confidence = 0.6
```

**Each parameter ends up carrying `{value, source, confidence, corridor}`.** This is shown on the dashboard: the user sees what they set themselves and what the system estimated.

**Important (v2.0): sparse user input is NOT penalized.** If the user gave few parameters, the missing ones are taken from tables/estimates (`derived`/`default`) — this is **normal operation, not a defect**. So in the current version the share of `default` parameters does **NOT** lower the overall `CONF` (the `c_assumptions` component is fixed, see §6.5). The "many defaults → lower confidence" link is deferred (if time remains) — it has merit, but it should not punish the user for simply not typing everything by hand. The parameter source is still shown on the dashboard for transparency — but it does not affect the confidence number right now.

---

## 6. STEP C — Indices (all deterministic)

Each index: formula, inputs, range, justification, effect. This is the heart of the answer to the professor — there is not a single eyeballed number here.

### 6.1 Seasonality index `SI`

**Formula:**
```
s[m] = mean(idx[t] for all t in month m) / mean(idx[t] over all t)   for m = 1..12
SI   = (max(s) − min(s)) / mean(s)
```

**Inputs:** the historical series (the same logic as the existing `seasonal_indices`).
**Range:** `[0, ~2]`. SI≈0 — flat business; SI>1 — extremely seasonal.
**Justification:** the span of the seasonal cycle relative to the mean level. A standard way to express "seasonal amplitude" with one number.
**Affects:**
- risk (§8.4): high seasonality → more months in the red → higher risk;
- break-even (§7.3): computed over the full yearly cycle with weights `s[m]`;
- cross-checked against `seasonality_expectation` from the LLM: a strong mismatch (LLM said `flat`, but SI=1.2) → a flag into confidence (§6.5).

**Data requirement:** reliable seasonality needs `L ≥ L_min` (24 mo). Less → SI is still computed, but confidence is lower via `c_data` (§6.5; short history → c_data < 1). This drop comes from *lack of history*, not from sparse user input — the latter is not penalized in v2.0.

### 6.2 Capital intensity index `CI`

**Formula:**
```
CI = I / monthly_revenue
```
where `monthly_revenue` is the average forecast monthly revenue (§7.2), `I` is initial investment (§7.4).

**Range:** `[0, ∞)`, practically 1–40.
**Justification:** how many months of revenue are "frozen" in the startup. Directly reflects the example: gas station (high CI) vs kebab shop (low CI).
**Affects:** the choice of payback profile — a cross-check of the LLM's `capital_intensity` category. If the LLM said `low` but CI=30 → a mismatch, a more conservative profile is taken.

### 6.3 Return index `ROI`

**Formula:**
```
ROI = (monthly_profit × 12) / I
```

**Range:** practically `[-0.5, 2]`.
**Justification:** classic annual ROI — return on invested capital. Understandable to any investor/jury without explanation.
**Affects:** score (§8.2) as one of the attractiveness components.

### 6.4 Payback index `PB`

**Formula:**
```
PB = I / monthly_profit          (if monthly_profit > 0)
PB = ∞                            (if monthly_profit ≤ 0)
```

**Range:** `[0, ∞)` months.
**Justification:** months to return the investment. A basic project-appraisal metric.
**Affects:** decision_label (§8.3) — compared against profile thresholds (§5.3), NOT a universal number. This is the threshold adaptivity.

### 6.5 Composite confidence index `CONF`

This is **the direct answer to the accuracy criterion**. Not a single MAPE, but a weighted blend of uncertainty sources.

**Components (each in [0,1], 1 = good):**

| Component | Formula | Justification |
|---|---|---|
| `c_forecast` | `clip(1 − mape / 0.5, 0, 1)` | Sybilion forecast accuracy. MAPE=0 → 1.0; MAPE≥0.5 → 0. The 0.5 threshold = a 50% error is treated as fully unreliable. |
| `c_data` | `clip(L / 60, 0, 1)` | History sufficiency. **5 years (60 mo) → 1.0**; linearly less (24 mo → 0.4, 12 mo → 0.2). Five years cover several seasonal cycles → confident estimate. Tied to `L_full` (§2.1). |
| `c_band` | `clip(1 − mean_relative_band_width, 0, 1)` | Forecast band tightness. A wide band (high−low)/forecast → lower. Computed **volume-weighted** (see below) so a seasonal dead month does not falsely lower it. |
| `c_assumptions` | **= 1.0 (fixed in v2.0)** | **Does NOT penalize sparse user input.** Missing parameters from tables are normal operation, not a defect. The "many defaults → lower CONF" link is deferred (§5.7). For now the component = 1.0, i.e. it does not affect confidence. |

**Blend (v2.0):** since `c_assumptions` is fixed at 1.0 and carries no information, there are **three active components**, and their weights are renormalized:
```
CONF = w1·c_forecast + w2·c_data + w3·c_band
weights: w1=0.50, w2=0.25, w3=0.25   (sum = 1)
```

**Weight justification:** forecast accuracy itself (`c_forecast`) is the main factor, hence the largest weight 0.50. History sufficiency and band tightness are equally important secondary sources at 0.25 each. The weights are fixed and justified here; they are not tuned to the result.

> Note for a future version: when we bring back the "penalty for defaults," `c_assumptions` becomes informative again (share of `user`/`derived`), and the weights return to the four-component scheme (e.g. 0.40/0.20/0.20/0.20). For now — three components, so as not to punish the user for sparse input.

**`c_band` volume-weighted (v2.0):** the relative width `(high−low)/forecast` is computed per month, but averaged **weighted by the forecast magnitude** of that month. Otherwise, for a strongly seasonal business (ice cream: summer 300, winter 30), dividing by a small winter `forecast` artificially inflates the relative width and falsely lowers `c_band`. Volume-weighting kills this artifact: the dead season has a small weight. Consistent with the volume-weighted break-even (§7.3).

**Range:** `[0, 1]`.
**Affects:** decision_label (§8.3, blocks Launch on low CONF), score (§8.2), and replaces the old formula `confidence_from_backtest = 0.86 − 1.5·mape` (which was two magic numbers).

**Replacing the old formula — sanity check:** at a typical demo MAPE=0.1, L=60, moderate band: c_forecast=0.8, c_data=1.0, c_band≈0.85 → CONF ≈ 0.50·0.8 + 0.25·1.0 + 0.25·0.85 = 0.86. The old formula gave 0.86−0.15=0.71. The new one is slightly higher (because we no longer penalize default assumptions) and is justified by three measurable sources.

---

## 7. STEP D — Economics core

### 7.1 Replacing `BASKETS_PER_INDEX_POINT` with a traceable `scale`

**Problem in the old code:** `revenue = index × 23.0 × price` — a single magic constant 23.

**New model — the bridge is decomposed and anchored:**
```
scale = how many transactions/month correspond to one index point
```
The source of `scale` is decided by a cascade (in descending order of honesty):

| Priority | Condition | How `scale` is computed | source |
|---|---|---|---|
| 1 | descriptions contain a traffic/transactions estimate | `scale = transactions_per_month / mean(idx)` | `derived` |
| 2 | user gave a target revenue estimate `R_target` | inverse problem: `scale = R_target / (mean(idx) × price × margin)` | `user` |
| 3 | nothing available | base by `ticket_class`: low→30, medium→12, high→5 transactions per index point | `default` |

**Justification of the defaults (item 3):** low-ticket businesses (ice cream) make many small transactions per demand unit; high-ticket ones (gas station) make few large ones. The numbers are an order-of-magnitude expert estimate, marked `default`.

**Result:** the magic 23 is gone. In its place — a chain with an explicit source, ideally tied to the user's data.

### 7.2 Monthly revenue

```
revenue[t] = idx[t] × scale × price
monthly_revenue = mean(revenue[t] over horizon H)
```

### 7.3 Profit and break-even

```
gross[t]  = revenue[t] × margin
profit[t] = gross[t] − fixed

# over the yearly cycle with seasonal weights (not a flat average):
annual_profit = Σ_{m=1..12} (mean_revenue × s[m] × margin − fixed)
monthly_profit = annual_profit / 12
```

**Break-even probability** — the probability that monthly profit > 0, accounting for forecast uncertainty.

**Replacing heavy Monte-Carlo with analytics** (fixes the 20,000-samples weak point):
```
σ_profit = monthly_revenue × margin × σ        (σ from §5.4)
break_even_probability = P(profit > 0)
                       = 1 − Φ( (fixed − mean_gross) / σ_profit )
```
where Φ is the standard normal CDF (12 `norm.cdf` calls over the cycle months, averaged — instead of 20,000 samples). Deterministic, no seed, instant.

**Justification:** under a normal approximation of forecast noise, the analytical formula gives the same answer as Monte-Carlo but reproducibly and at no compute cost. **Sanity requirement:** verify that on the demo data it gives break-even around 0.55–0.60 (so the baseline verdict stays "Adapt concept").

**downside / upside** — the 10th and 90th percentiles of monthly profit:
```
downside = mean_profit − Z_P90 × σ_profit
upside   = mean_profit + Z_P90 × σ_profit
```

### 7.4 Investment — two-way estimate

Instead of one heuristic — **two independent estimates + a cross-check**:

**Top-down (from scale):**
```
I_topdown = monthly_revenue × CI_target
```
where `CI_target` is the target capital intensity from the profile (§5.3, converted to a multiplier on revenue).

**Bottom-up (from line items):**
```
I_bottomup = setup + inventory + marketing + legal + cash_buffer
```
by components (the existing `compute_investment` logic, but with bases from §5.3 by profile, not a fixed 72,000).

**Cross-check:**
```
I = (I_topdown + I_bottomup) / 2
divergence = |I_topdown − I_bottomup| / I
```
`divergence` is an **uncertainty signal**: a large gap between the two methods → the investment estimate is unreliable → it feeds into risk (§8.4) and is mentioned in the explanation. This turns a weak spot into a feature: the model honestly says "the two methods disagreed."

---

## 8. STEP E — Decision (multi-dimensional)

**Problem in the old code:** `_decision_label` looked only at break-even (one-dimensional); backtest/risk/payback did not affect the verdict.

**New model:** the verdict comes from **four dimensions**, each from the indices above.

### 8.1 The four verdict dimensions

| Dimension | Source | "Good" threshold |
|---|---|---|
| Viability | `break_even_probability` (§7.3) | ≥ 0.6 |
| Payback | `PB` vs profile (§6.4, §5.3) | PB ≤ profile's normal payback |
| Confidence | `CONF` (§6.5) | ≥ 0.6 |
| Risk | `risk_level` (§8.4) | ≤ medium |

### 8.2 Score (0–100) — showcase metric

```
score = 100 × (
    0.35 · be_score      +   # normalized break-even probability
    0.25 · pb_score      +   # payback relative to profile, normalized
    0.20 · roi_score     +   # normalized ROI
    0.20 · conf_score        # CONF
)
```
**Weight justification:** viability (be) is primary → 0.35; payback → 0.25; return and confidence → 0.20 each. Sum = 1. Each component is normalized to [0,1] over the ranges in §6.

(Replaces the old `_score = 0.45·break_even + 0.55·profit_score` — now four components instead of two, all justified.)

### 8.3 decision_label — adaptive thresholds via profiles

**Key principle:** thresholds do NOT float freely (that would be uninterpretable and over-fittable). Thresholds are **taken from the payback profile** (§5.3), chosen by the `capital_intensity` category. This gives adaptivity without arbitrariness.

**Logic:**
```
# payback is judged relative to the business PROFILE:
pb_ok        = PB ≤ profile.normal_payback
pb_tolerable = PB ≤ profile.tolerable_payback

IF break_even ≥ 0.6 AND pb_ok AND CONF ≥ 0.6 AND risk ≤ medium:
    label = "Launch"
ELIF break_even ≥ 0.5 AND pb_tolerable AND CONF ≥ 0.45:
    label = "Adapt concept"
ELIF break_even ≥ 0.4:
    label = "Delay"
ELSE:
    label = "Do not launch"

# hard overrides:
IF CONF < 0.4:  label = max(label, "Delay")            # no Launch on unreliable data
IF mape > 0.4:  label = max(label, "Adapt concept")    # weak backtest blocks Launch
```

**Threshold justification:**
- break-even 0.6 for Launch = profitable in most months of the cycle;
- payback relative to profile = a `very_high` gas station with PB=70 passes (profile tolerates 96), a `low` kebab shop with PB=70 does not (profile tolerates 24) — solves the type-dependence case;
- the CONF override = **direct protection against bullshit**: the model does not say Launch if it is not confident in the data;
- the mape override = a weak forecast gives no green light.

**This makes the verdict multi-dimensional:** the label now depends on break-even AND payback AND confidence AND risk — not on break-even alone as before.

### 8.4 risk_level

```
risk_score = (
    0.40 · σ_norm           +   # demand volatility (§5.4)
    0.30 · seasonality_norm +   # normalized SI (§6.1)
    0.20 · band_norm        +   # forecast band width
    0.10 · divergence_norm      # investment-estimate divergence (§7.4)
)
label_risk = low (if <0.33) / medium (<0.66) / high (otherwise)
```
**Weight justification:** demand volatility is the main risk driver (0.40); seasonality is a significant secondary one (0.30, a strongly seasonal business is riskier); band width (0.20); investment-method divergence (0.10, an auxiliary signal).

(Replaces the old `_risk_level`, which depended only on band width.)

---

## 9. STEP F — Explanation (LLM over finished numbers)

**Principle:** the LLM receives **only the computed numbers and categories**. It cannot invent new ones, change the verdict, or change the numbers. It only phrases them in words.

### 9.1 What is passed to the LLM

```json
{
  "label": "Adapt concept",
  "score": 62,
  "break_even_probability": 0.57,
  "payback_months": 31,
  "payback_profile": "medium (normal 24, tolerable 42)",
  "confidence": 0.79,
  "risk_level": "medium",
  "monthly_revenue": 18500,
  "monthly_profit": 2100,
  "roi": 0.31,
  "top_drivers": [{"name": "...", "direction": "...", "importance": "..."}],
  "key_assumptions": [{"param": "rent", "value": 6000, "source": "default"}],
  "seasonality_index": 0.9,
  "investment_divergence": 0.15
}
```

### 9.2 Strict prompt constraints

The prompt must contain:
1. "You are explaining an ALREADY-MADE decision. Changing the numbers or the verdict is FORBIDDEN."
2. "Use ONLY the numbers from the input JSON. Inventing new numbers, percentages, or amounts is FORBIDDEN."
3. "Every statement must reference a specific driver or number from the input."
4. "If there is no input data for a statement — do not make the statement."
5. Structured output: `{main_reason, positive_factors[], negative_factors[], recommended_actions[]}`.

### 9.3 LLM output validation

After generation — a check:
- the output is valid JSON of the expected structure;
- **numbers in the text are checked against the inputs**: if the LLM mentioned a number not in the input JSON (with a rounding tolerance) → the output is rejected, fall back to the template;
- the verdict in the text matches `label` → otherwise rejected.

**Fallback (by mode, P6 / §1.1):** on any LLM failure or validation failure —
- **`prod`:** a deterministic template from the numbers (the existing `build_reason` logic) + a message in `runtime.fallbacks`. The text is always present.
- **`dev`:** an error (we want to see that the LLM explanation did not work).

**This is the "not bullshit" guarantee:** the LLM physically has nothing on its input except our numbers, and the validator catches any invented number.

---

## 10. Number → spec section correspondence table

A review checklist (principle P4). Every constant/coefficient in `report_agent.py` must be found here.

| What in code | Value | Section | Type |
|---|---|---|---|
| Horizon H | from contract (default 6, 1..12) | §2.1, §2.2 | structural (request parameter) |
| Min history L_min | 24 | §2.1 | structural |
| History for full confidence L_full | 60 | §2.1, §6.5 | structural |
| Z_P90 | 1.2816 | §2.1 | mathematical |
| Basket bases | 6/25/60 | §5.1 | expert (default) |
| Margin bases | 0.20/0.50/0.70 | §5.2 | expert |
| Investment bases (5 levels) | 12k/25k/80k/250k/600k | §5.3 | expert |
| Normal payback (5 levels) | 8/12/24/42/60 | §5.3 | expert |
| Tolerable payback (5 levels) | 15/24/42/72/96 | §5.3 | expert |
| σ demand_breadth | 0.10/0.18/0.28 | §5.4 | expert |
| σ perishability | 0/0.03/0.06 | §5.4 | expert |
| σ external_shock_sensitivity | 0/0.04/0.08 | §5.4 | expert |
| σ corridor | [0.10, 0.35] | §5.4 | protective |
| fixed bases | 6000/9000/2400 | §5.6 | expert (default) |
| scale defaults | 30/12/5 | §7.1 | expert (default) |
| MAPE threshold in c_forecast | 0.5 | §6.5 | justified |
| c_data anchor | 60 mo → 1.0 | §6.5 | justified |
| c_assumptions (fixed) | 1.0 | §6.5 | protective (does not penalize input) |
| CONF weights (3 components) | 0.50/0.25/0.25 | §6.5 | justified |
| score weights | 0.35/0.25/0.20/0.20 | §8.2 | justified |
| label thresholds (be) | 0.6/0.5/0.4 | §8.3 | justified |
| CONF/mape overrides | 0.4/0.4 | §8.3 | protective |
| risk weights | 0.40/0.30/0.20/0.10 | §8.4 | justified |

**Number types:**
- **structural** — a problem parameter, not tuned;
- **mathematical** — from theory (a normal percentile);
- **expert** — our order-of-magnitude estimate, marked as an assumption, ideally overridden by user data;
- **justified** — chosen deliberately with logic in the text;
- **protective** — a floor/ceiling against degenerate behavior.

Not a single "where did this come from" number. That is exactly the accuracy criterion.

---

## 11. What changes in the code vs the current report_agent.py

A compact implementation map.

| Current | Becomes | Phase |
|---|---|---|
| `BASKETS_PER_INDEX_POINT = 23.0` | `scale` cascade §7.1 | 3 |
| `Assumptions` fixed dataclass | cascade §5.7 with sources | 2 |
| `FORECAST_HORIZON = 6` (hard-coded) | request-contract parameter §2.2 | 2 |
| `seasonal_indices()` | + the SI index §6.1 | 2 |
| (no profiler) | LLM profiler §3 (8 axes) | 2 |
| (no reference tables) | tables §5 | 2 |
| (no modes) | `dev`/`prod` + `runtime.fallbacks` §1.1 | 2 |
| Monte-Carlo 20,000 samples | analytics §7.3 | 3 |
| `compute_investment()` heuristic | two-way + cross-check §7.4 | 3 |
| `confidence_from_backtest` (2 numbers) | CONF §6.5 (3 components, c_data over 5 years) | 4 |
| `_decision_label` one-dimensional | multi-dimensional §8.3 | 4 |
| `_score` (2 components) | §8.2 (4 components) | 4 |
| `_risk_level` (band) | §8.4 (4 components) | 4 |
| `_SUMMARY` 4 texts | LLM §9 | 5 |
| `build_reason` templates | LLM §9 + validation | 5 |
| double cross-check reference/subprocess | reference = main, mock = only on error (in `dev`, an error) | 5 |

---

## 12. What to show the jury (defense cheatsheet)

When asked "where do the numbers come from / why trust the model":

1. **"No ground truth, so we measure three things"** → §0 P1. We do not claim to predict reality; we compute consistency + calibration + traceability.
2. **"The LLM does not invent the result"** → §0 P2. The LLM classifies and explains, code computes. Show §3 (classification into categories) and §9 (explanation with a validator that catches invented numbers).
3. **"Every number is justified"** → §10 the correspondence table. Open it and show that for any constant there is a row with a type and a justification.
4. **"The model adapts to business type"** → §5.3 + §8.3. Gas station vs kebab shop: different payback profiles → different verdict thresholds. Not over-fitting, but justified profiles.
5. **"Confidence is honest"** → §6.5. Not a single MAPE, but several uncertainty sources; on unreliable data the model blocks Launch itself (§8.3). And we do NOT punish the user for sparse input — the missing values come from justified tables.
6. **"We do not hide failures"** → §1.1. `prod` mode always reports when a result is on a fallback (`runtime.fallbacks`); `dev` mode has no fallbacks at all and fails on any error, so during development we are not fooled by synthetic data.

---

*End of specification v2.0. Numbers of the "expert" type are order-of-magnitude assumptions, openly marked as assumptions; they are refined by user data via the cascade (§5.7) and are a deliberate engineering choice, not guessing. Sparse user input is not penalized (§6.5); the `dev`/`prod` modes define behavior on failure (§1.1).*