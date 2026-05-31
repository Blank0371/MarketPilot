"""Report agent (Block 4) for MarketPilot — v2.0 decision model.

Implements the decision model specified in ``backend/MODEL.md`` (the source of
truth for every formula, table, constant, and threshold). The shape of the
report matches ``ARCHITECTURE.md`` §5.6 plus a ``runtime`` block.

The one rule that defines this module (MODEL.md §0, P2):

    **The LLM classifies and explains; deterministic Python computes every
    number and the verdict.**

* STEP A — an LLM *profiler* classifies the business onto 8 axes (categories
  only, never numbers; §3).
* STEP B — deterministic code maps categories → coefficients via the §5 tables
  and the §5.7 resolution cascade.
* STEP C — deterministic indices: seasonality, capital intensity, ROI, payback,
  and the composite confidence ``CONF`` (§6).
* STEP D — deterministic economics: a traceable ``scale`` cascade (§7.1),
  revenue/profit, an **analytical** break-even via the normal CDF (§7.3, no
  Monte-Carlo), and a two-way investment estimate (§7.4).
* STEP E — the multi-dimensional verdict: ``score``, ``decision_label`` with
  profile-relative payback thresholds, and ``risk_level`` (§8).
* STEP F — an LLM *phrases* the reason over the already-computed numbers, and a
  validator rejects any invented number or verdict (§9).

Run modes (MODEL.md §1.1 / P6): ``MODEL_MODE=dev|prod`` (default ``prod``). In
``dev`` any failure raises; in ``prod`` documented loud fallbacks fire and each
is recorded in ``runtime.fallbacks``.

Public surface (kept importable + orchestrator-friendly):

    build_report(timeseries, metadata, user_input, descriptions,
                 *, forecast_horizon_months=6, forecast_bundle=None,
                 business_profile=None) -> dict
    prepare_context(...) -> ReportContext     # fetch forecast once, bundle inputs
    recompute(context, overrides) -> dict      # what-if, reuses the cached forecast
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import sybilion_client

logger = logging.getLogger("marketpilot.report_agent")

# ===========================================================================
# §2.1 — Fixed structural constants (problem parameters, not tuned)
# ===========================================================================
DEFAULT_HORIZON = 6              # see MODEL.md §2.1, §2.2 — request default
HORIZON_MIN, HORIZON_MAX = 1, 12  # see MODEL.md §2.2 — clamp range
L_MIN = 24                       # see MODEL.md §2.1 — min history for reliable seasonality
L_FULL = 60                      # see MODEL.md §2.1, §6.5 — history for full c_data confidence
MONTHS_PER_YEAR = 12             # see MODEL.md §2.1 — calendar
Z_P90 = 1.2816                   # see MODEL.md §2.1 — 90th percentile of the standard normal


def _run_mode() -> str:
    """Resolve the run mode (MODEL.md §1.1). Read at call time so tests can patch."""
    mode = os.environ.get("MODEL_MODE", "prod").strip().lower()
    return mode if mode in ("dev", "prod") else "prod"


def _normal_cdf(x: float) -> float:
    """Standard normal CDF Φ(x) via the error function — exact, no scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _clamp01(x: float) -> float:
    return _clamp(x, 0.0, 1.0)


# ===========================================================================
# §3 — Profiler axes, enums, and the neutral fallback profile
# ===========================================================================
# Closed value lists per axis (MODEL.md §3.2). Order is low → high where it matters.
AXIS_VALUES: dict[str, list[str]] = {
    "capital_intensity": ["very_low", "low", "medium", "high", "very_high"],  # §3.2, §3.2.1 (5 levels)
    "perishability": ["none", "low", "high"],                                  # §3.2
    "seasonality_expectation": ["flat", "moderate", "strong"],                 # §3.2
    "demand_breadth": ["mass", "mixed", "niche"],                              # §3.2
    "margin_class": ["low", "medium", "high"],                                 # §3.2
    "ticket_class": ["low", "medium", "high"],                                 # §3.2
    "purchase_frequency": ["daily", "periodic", "rare"],                       # §3.2
    "external_shock_sensitivity": ["low", "medium", "high"],                   # §3.2
}

# Documented "middle" value per axis — used when an enum is violated or the LLM
# is unavailable in prod (MODEL.md §3.4).
AXIS_MIDDLE: dict[str, str] = {
    "capital_intensity": "medium",
    "perishability": "low",
    "seasonality_expectation": "moderate",
    "demand_breadth": "mixed",
    "margin_class": "medium",
    "ticket_class": "medium",
    "purchase_frequency": "periodic",
    "external_shock_sensitivity": "medium",
}


def neutral_profile() -> dict[str, Any]:
    """The all-middle profile used as the prod fallback when the LLM is unavailable (§3.4)."""
    profile = dict(AXIS_MIDDLE)
    profile["reasoning"] = "Neutral profile (LLM unavailable): middle value on every axis."
    profile["confidence"] = 0.0
    return profile


def guard_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce a raw profile to valid enums; any out-of-list value → the middle (§3.4)."""
    raw = raw or {}
    profile: dict[str, Any] = {}
    for axis, allowed in AXIS_VALUES.items():
        value = str(raw.get(axis, "")).strip().lower()
        profile[axis] = value if value in allowed else AXIS_MIDDLE[axis]
    profile["reasoning"] = str(raw.get("reasoning", "") or "")[:600]
    try:
        profile["confidence"] = _clamp01(float(raw.get("confidence", 0.5)))  # self-assessment only — NOT used in CONF (§3.3, §6.5)
    except (TypeError, ValueError):
        profile["confidence"] = 0.5
    return profile


# ===========================================================================
# §5 — Coefficient reference tables (defaults). Every value cites its section.
# ===========================================================================
# §5.1 — Average basket by ticket_class: {value: base €, corridor: (lo, hi)}
BASKET_BASE = {"low": 6.0, "medium": 25.0, "high": 60.0}              # see MODEL.md §5.1
BASKET_CORRIDOR = {"low": (3.0, 10.0), "medium": (10.0, 60.0), "high": (40.0, 150.0)}  # see MODEL.md §5.1

# §5.2 — Gross margin by margin_class (fraction)
MARGIN_BASE = {"low": 0.20, "medium": 0.50, "high": 0.70}            # see MODEL.md §5.2
MARGIN_CORRIDOR = {"low": (0.10, 0.30), "medium": (0.35, 0.65), "high": (0.60, 0.85)}  # see MODEL.md §5.2

# §5.3 — Payback profile by capital_intensity: (base investment €, normal mo, tolerable mo)
PAYBACK_PROFILE = {
    "very_low":  (12_000.0, 8, 15),    # see MODEL.md §5.3
    "low":       (25_000.0, 12, 24),   # see MODEL.md §5.3
    "medium":    (80_000.0, 24, 42),   # see MODEL.md §5.3
    "high":      (250_000.0, 42, 72),  # see MODEL.md §5.3
    "very_high": (600_000.0, 60, 96),  # see MODEL.md §5.3
}

# §7.4 — Target capital intensity (months of revenue "frozen" in startup) per
# profile, derived from §5.3 base investment ÷ a representative monthly revenue
# (≈ §6.2 range 1–40). Used for the top-down investment estimate.
CI_TARGET = {
    "very_low": 1.5, "low": 1.7, "medium": 2.0, "high": 3.0, "very_high": 5.0,  # see MODEL.md §7.4, §6.2
}

# §5.4 — Demand volatility σ as a fraction of mean demand, built from three axes.
SIGMA_BREADTH = {"mass": 0.10, "mixed": 0.18, "niche": 0.28}         # see MODEL.md §5.4
SIGMA_PERISH = {"none": 0.00, "low": 0.03, "high": 0.06}             # see MODEL.md §5.4
SIGMA_SHOCK = {"low": 0.00, "medium": 0.04, "high": 0.08}           # see MODEL.md §5.4
SIGMA_CORRIDOR = (0.10, 0.35)                                        # see MODEL.md §5.4 (protective floor/ceiling)

# §5.6 — Fixed-cost component bases (€/mo)
FIXED_BASE = {"rent": 6_000.0, "staff": 9_000.0, "other": 2_400.0}  # see MODEL.md §5.6

# §7.1 — scale defaults (transactions per index point) by ticket_class
SCALE_DEFAULT = {"low": 30.0, "medium": 12.0, "high": 5.0}          # see MODEL.md §7.1

# §8.2 — score component weights
SCORE_W = {"be": 0.35, "pb": 0.25, "roi": 0.20, "conf": 0.20}       # see MODEL.md §8.2
# §8.4 — risk component weights
RISK_W = {"sigma": 0.40, "season": 0.30, "band": 0.20, "divergence": 0.10}  # see MODEL.md §8.4
# §6.5 — CONF weights (three active components; c_assumptions is fixed at 1.0)
CONF_W = {"forecast": 0.50, "data": 0.25, "band": 0.25}            # see MODEL.md §6.5


# ===========================================================================
# §5.7 — Assumption resolution cascade (the P3 mechanism)
# ===========================================================================
@dataclass(frozen=True)
class ResolvedParam:
    """A parameter resolved by the cascade: value + provenance (MODEL.md §5.7)."""

    value: float
    source: str           # "user" | "derived" | "default" | "llm_adjusted"
    confidence: float     # 1.0 user / 0.7 derived / 0.5 default / 0.6 llm_adjusted
    corridor: tuple[float, float] | None = None


# Cascade confidence by source (MODEL.md §5.7). NOTE: these confidences are shown
# on the dashboard for transparency but do NOT feed CONF — sparse user input is
# not penalized in v2.0 (§5.7, §6.5: c_assumptions is fixed at 1.0).
_SRC_CONF = {"user": 1.0, "derived": 0.7, "default": 0.5, "llm_adjusted": 0.6}


def _resolve(
    name: str,
    user_params: dict[str, Any],
    default_value: float,
    *,
    derived_value: float | None = None,
    corridor: tuple[float, float] | None = None,
) -> ResolvedParam:
    """Resolve one parameter: user → derived → default (MODEL.md §5.7).

    A user-provided value wins outright (source ``user``) and is NOT clamped to
    the corridor — their own data overrides the table. The optional in-corridor
    LLM nudge (``llm_adjusted``) is deferred in v2.0, exactly as §5.7 defers the
    "penalty for defaults": fewer LLM round-trips, fully deterministic economics.
    """
    if user_params.get(name) is not None:
        return ResolvedParam(float(user_params[name]), "user", _SRC_CONF["user"], corridor)
    if derived_value is not None:
        return ResolvedParam(float(derived_value), "derived", _SRC_CONF["derived"], corridor)
    return ResolvedParam(float(default_value), "default", _SRC_CONF["default"], corridor)


def resolve_parameters(profile: dict[str, Any], user_params: dict[str, Any]) -> dict[str, ResolvedParam]:
    """Map profile categories → coefficients via §5 tables + the §5.7 cascade.

    The "derived" tier (rent from area×district rate, staff from headcount, §5.6)
    fires only when such data is present; for free-text demos it is absent and
    the table default is used — normal operation, not a defect (§5.7).
    """
    ticket = profile["ticket_class"]
    margin_class = profile["margin_class"]

    basket = _resolve("basket", user_params, BASKET_BASE[ticket], corridor=BASKET_CORRIDOR[ticket])  # §5.1
    margin = _resolve("margin", user_params, MARGIN_BASE[margin_class], corridor=MARGIN_CORRIDOR[margin_class])  # §5.2
    # Keep margin a sane fraction even if the user typed something out of range.
    margin = replace(margin, value=_clamp01(margin.value))
    basket = replace(basket, value=max(0.01, basket.value))

    rent = _resolve("rent", user_params, FIXED_BASE["rent"])    # §5.6
    staff = _resolve("staff", user_params, FIXED_BASE["staff"])  # §5.6
    other = _resolve("other", user_params, FIXED_BASE["other"])  # §5.6
    return {"basket": basket, "margin": margin, "rent": rent, "staff": staff, "other": other}


# ===========================================================================
# §6.1 — Seasonal profile + Seasonality index SI
# ===========================================================================
def seasonal_indices(timeseries: dict[str, float]) -> dict[int, float]:
    """Average month-of-year multipliers s[m], normalized to mean 1.0 (MODEL.md §6.1)."""
    by_month: dict[int, list[float]] = {}
    for key, value in timeseries.items():
        by_month.setdefault(date.fromisoformat(key).month, []).append(float(value))
    if not by_month:
        return {m: 1.0 for m in range(1, 13)}
    month_avg = {m: sum(vs) / len(vs) for m, vs in by_month.items()}
    overall = sum(month_avg.values()) / len(month_avg)
    if overall <= 0:
        return {m: 1.0 for m in range(1, 13)}
    # Fill any missing month with the neutral 1.0 so a short series still works.
    return {m: month_avg.get(m, overall) / overall for m in range(1, 13)}


def seasonality_index(seasonal: dict[int, float]) -> float:
    """SI = (max(s) − min(s)) / mean(s) — the seasonal amplitude (MODEL.md §6.1).

    Range [0, ~2]: SI≈0 flat, SI>1 extremely seasonal.
    """
    s = list(seasonal.values())
    mean_s = sum(s) / len(s) if s else 1.0
    if mean_s <= 0:
        return 0.0
    return (max(s) - min(s)) / mean_s


# ===========================================================================
# §6.5 — Composite confidence index CONF
# ===========================================================================
def forecast_band_width(forecast: list[dict]) -> float:
    """Volume-weighted relative forecast band width = Σ(high−low) / Σ(forecast).

    Weighting by forecast magnitude (MODEL.md §6.5) prevents a seasonal dead
    month (small denominator) from falsely inflating the relative width.
    """
    total_span = sum(max(0.0, p["high"] - p["low"]) for p in forecast)
    total_level = sum(max(0.0, p["forecast"]) for p in forecast)
    return total_span / total_level if total_level > 0 else 0.0


def confidence_index(mape: float, history_len: int, rel_band_width: float) -> dict[str, float]:
    """The composite confidence CONF — a blend of three uncertainty sources (§6.5).

    Returns the components and the blended value (for the dashboard/audit).
    """
    c_forecast = _clamp01(1.0 - mape / 0.5)         # see MODEL.md §6.5 — MAPE≥0.5 ⇒ fully unreliable
    c_data = _clamp01(history_len / L_FULL)          # see MODEL.md §6.5 — 60 mo ⇒ 1.0
    c_band = _clamp01(1.0 - rel_band_width)          # see MODEL.md §6.5 — wide band ⇒ lower
    c_assumptions = 1.0                              # see MODEL.md §6.5 — fixed; does NOT penalize sparse input
    conf = CONF_W["forecast"] * c_forecast + CONF_W["data"] * c_data + CONF_W["band"] * c_band  # §6.5
    return {
        "CONF": round(conf, 4),
        "c_forecast": round(c_forecast, 4),
        "c_data": round(c_data, 4),
        "c_band": round(c_band, 4),
        "c_assumptions": c_assumptions,
    }


# ===========================================================================
# §7 — Economics core
# ===========================================================================
def _demand_sigma(profile: dict[str, Any]) -> float:
    """Final demand volatility σ from three axes, clamped to the corridor (§5.4)."""
    sigma = (
        SIGMA_BREADTH[profile["demand_breadth"]]            # §5.4
        + SIGMA_PERISH[profile["perishability"]]            # §5.4
        + SIGMA_SHOCK[profile["external_shock_sensitivity"]]  # §5.4
    )
    return _clamp(sigma, *SIGMA_CORRIDOR)                    # §5.4 corridor [0.10, 0.35]


def resolve_scale(
    profile: dict[str, Any],
    user_params: dict[str, Any],
    level_idx: float,
    price: float,
    margin: float,
) -> ResolvedParam:
    """The §7.1 scale cascade — replaces the old magic ``BASKETS_PER_INDEX_POINT``.

    ``scale`` = transactions/month per one forecast index point. ``level_idx`` is
    the de-seasonalized demand level (so the bridge is anchored on a typical
    month, consistent with the full-year break-even in §7.3).
    """
    level_idx = max(level_idx, 1e-9)
    # Priority 1 — a traffic/transactions estimate is available (source: derived). §7.1
    if user_params.get("transactions") is not None:
        return ResolvedParam(float(user_params["transactions"]) / level_idx, "derived", _SRC_CONF["derived"])
    # Priority 2 — the user gave a target (gross) revenue R_target (source: user). §7.1
    if user_params.get("target_revenue") is not None and price > 0 and margin > 0:
        scale = float(user_params["target_revenue"]) / (level_idx * price * margin)
        return ResolvedParam(scale, "user", _SRC_CONF["user"])
    # Priority 3 — table base by ticket_class (source: default). §7.1
    return ResolvedParam(SCALE_DEFAULT[profile["ticket_class"]], "default", _SRC_CONF["default"])


def compute_economics(
    forecast: list[dict],
    seasonal: dict[int, float],
    scale: float,
    price: float,
    margin: float,
    fixed: float,
    sigma: float,
) -> dict[str, Any]:
    """Revenue → profit → analytical break-even → downside/upside (MODEL.md §7.2, §7.3).

    The headline revenue/costs/profit triple is the **de-seasonalized annual-average
    month** (so revenue − costs = profit, internal consistency P1), and the
    break-even is averaged over the full yearly cycle with the seasonal weights
    s[m] — the dominant risk for a seasonal business. (We read §7.2's "mean over
    the horizon" as estimating the demand *level*, then de-seasonalize it; using
    the raw summer-biased horizon mean as the annual mean would over-state a
    seasonal business and contradict §7.3's "over the yearly cycle".)
    """
    idx = [float(p["forecast"]) for p in forecast]
    months = [date.fromisoformat(p["date"]).month for p in forecast]
    mean_idx_horizon = sum(idx) / len(idx) if idx else 0.0                    # §7.2 mean over horizon
    seasonal_horizon = sum(seasonal.get(m, 1.0) for m in months) / len(months) if months else 1.0
    seasonal_horizon = seasonal_horizon or 1.0
    level_idx = mean_idx_horizon / seasonal_horizon                          # de-seasonalized demand level

    monthly_revenue = level_idx * scale * price                              # §7.2 revenue = idx × scale × price
    monthly_gross = monthly_revenue * margin                                 # §7.3 gross = revenue × margin
    monthly_profit = monthly_gross - fixed                                   # §7.3 profit = gross − fixed (annual-avg)
    monthly_costs = monthly_revenue - monthly_profit                         # COGS + fixed, consistent with the triple

    # Break-even probability — analytical, deterministic, no Monte-Carlo (§7.3).
    # σ_profit = monthly_revenue × margin × σ; average 12 norm.cdf calls over the cycle.
    sigma_profit = max(monthly_revenue * margin * sigma, 1e-9)               # §7.3
    per_month_be = []
    for m in range(1, 13):
        mean_gross_m = monthly_revenue * seasonal.get(m, 1.0) * margin       # §7.3 mean_revenue × s[m] × margin
        per_month_be.append(1.0 - _normal_cdf((fixed - mean_gross_m) / sigma_profit))  # §7.3 P(profit>0)
    break_even = sum(per_month_be) / len(per_month_be)

    downside = monthly_profit - Z_P90 * sigma_profit                         # §7.3 p10 of monthly profit
    upside = monthly_profit + Z_P90 * sigma_profit                           # §7.3 p90 of monthly profit

    return {
        "expected_monthly_revenue_eur": round(monthly_revenue),
        "expected_monthly_costs_eur": round(monthly_costs),
        "expected_monthly_profit_eur": round(monthly_profit),
        "downside_monthly_profit_eur": round(downside),
        "upside_monthly_profit_eur": round(upside),
        "break_even_probability": round(break_even, 2),
        # Raw values for the indices/decision (stripped before the response):
        "_monthly_revenue": monthly_revenue,
        "_monthly_profit": monthly_profit,
        "_sigma": sigma,
        "_sigma_profit": sigma_profit,
        "_level_idx": level_idx,
    }


def compute_investment(profile: dict[str, Any], monthly_revenue: float) -> dict[str, Any]:
    """Two-way investment estimate + a cross-check divergence (MODEL.md §7.4).

    * top-down  : monthly_revenue × CI_target (months of revenue frozen)
    * bottom-up : the profile's base investment from §5.3 (the line-item anchor)
    * I = mean of the two; divergence = |top−bottom| / I is an uncertainty signal.

    The returned breakdown sums **exactly** to ``estimated_initial_investment_eur``
    (a contract invariant checked by tests).
    """
    capital = profile["capital_intensity"]
    base_investment = PAYBACK_PROFILE[capital][0]                  # §5.3 base (bottom-up anchor)
    i_topdown = monthly_revenue * CI_TARGET[capital]              # §7.4 top-down
    i_bottomup = base_investment                                  # §7.4 bottom-up
    investment = (i_topdown + i_bottomup) / 2.0                   # §7.4 cross-check average
    investment = max(investment, 1.0)
    divergence = abs(i_topdown - i_bottomup) / investment        # §7.4 uncertainty signal → risk (§8.4)

    total = round(investment)
    # Allocate the total across line items by justified proportions (§5.6 example
    # in ARCHITECTURE §5.6). The largest item absorbs the rounding so the sum is exact.
    proportions = [
        ("Store setup", 0.37),
        ("Initial inventory", 0.25),
        ("Cash buffer", 0.17),
        ("Launch marketing", 0.13),
        ("Legal and licensing", 0.08),
    ]
    breakdown = [{"category": name, "amount": round(total * p)} for name, p in proportions]
    breakdown[0]["amount"] += total - sum(item["amount"] for item in breakdown)  # exact sum invariant
    return {
        "estimated_initial_investment_eur": total,
        "breakdown": breakdown,
        "_divergence": divergence,
        "_i_topdown": i_topdown,
        "_i_bottomup": i_bottomup,
    }


# ===========================================================================
# §6.2–§6.4 — Capital-intensity, ROI, payback indices
# ===========================================================================
def capital_intensity_index(investment: float, monthly_revenue: float) -> float:
    """CI = I / monthly_revenue — months of revenue frozen in the startup (§6.2)."""
    return investment / monthly_revenue if monthly_revenue > 0 else float("inf")


def roi_index(monthly_profit: float, investment: float) -> float:
    """ROI = (monthly_profit × 12) / I — classic annual return on capital (§6.3)."""
    return (monthly_profit * MONTHS_PER_YEAR) / investment if investment > 0 else 0.0


def payback_index(investment: float, monthly_profit: float) -> float:
    """PB = I / monthly_profit, or ∞ if profit ≤ 0 (§6.4)."""
    return investment / monthly_profit if monthly_profit > 0 else float("inf")


# ===========================================================================
# §8 — Decision (multi-dimensional)
# ===========================================================================
_LABEL_RANK = {"Do not launch": 0, "Delay": 1, "Adapt concept": 2, "Launch": 3}


def _cap_at(label: str, ceiling: str) -> str:
    """Return the *more pessimistic* of two labels (the §8.3 'max(label, ...)' override)."""
    return label if _LABEL_RANK[label] <= _LABEL_RANK[ceiling] else ceiling


def compute_score(break_even: float, pb: float, tolerable_payback: int, roi: float, conf: float) -> int:
    """score 0–100 from four normalized components (MODEL.md §8.2)."""
    be_score = _clamp01(break_even)                                   # §8.2 viability
    pb_score = _clamp01(1.0 - pb / tolerable_payback) if math.isfinite(pb) else 0.0  # §8.2 payback vs profile
    roi_score = _clamp01((roi + 0.5) / 2.5)                           # §8.2 ROI normalized over ~[-0.5, 2] (§6.3)
    conf_score = _clamp01(conf)                                       # §8.2 confidence
    score = SCORE_W["be"] * be_score + SCORE_W["pb"] * pb_score + SCORE_W["roi"] * roi_score + SCORE_W["conf"] * conf_score
    return int(round(100 * _clamp01(score)))


def compute_risk(sigma: float, si: float, rel_band_width: float, divergence: float) -> dict[str, Any]:
    """risk_level from four normalized components (MODEL.md §8.4)."""
    sigma_norm = _clamp01((sigma - SIGMA_CORRIDOR[0]) / (SIGMA_CORRIDOR[1] - SIGMA_CORRIDOR[0]))  # §8.4 over the σ corridor
    season_norm = _clamp01(si / 1.0)        # §8.4 — SI≥1 is "extremely seasonal" (§6.1) ⇒ risk ceiling
    band_norm = _clamp01(rel_band_width / 0.5)  # §8.4 — relative band width
    divergence_norm = _clamp01(divergence)  # §8.4 — investment-method divergence (§7.4)
    risk_score = (
        RISK_W["sigma"] * sigma_norm
        + RISK_W["season"] * season_norm
        + RISK_W["band"] * band_norm
        + RISK_W["divergence"] * divergence_norm
    )
    if risk_score < 0.33:        # §8.4 thresholds
        level = "Low"
    elif risk_score < 0.66:
        level = "Medium"
    else:
        level = "High"
    return {"risk_level": level, "risk_score": round(risk_score, 4)}


def decision_label(break_even: float, pb: float, profile_payback: tuple[int, int], conf: float, risk_level: str, mape: float) -> str:
    """The adaptive, multi-dimensional verdict (MODEL.md §8.3).

    Thresholds for payback come from the business PROFILE (§5.3), not a universal
    number — a very-high-capital gas station and a low-capital kebab shop are
    judged against their own norms.
    """
    normal_payback, tolerable_payback = profile_payback
    pb_ok = pb <= normal_payback              # §8.3 — within the profile's normal payback
    pb_tolerable = pb <= tolerable_payback    # §8.3 — within the profile's tolerable payback
    risk_ok = risk_level in ("Low", "Medium")  # §8.3 — risk ≤ medium

    if break_even >= 0.6 and pb_ok and conf >= 0.6 and risk_ok:   # §8.3 thresholds (be 0.6 / CONF 0.6)
        label = "Launch"
    elif break_even >= 0.5 and pb_tolerable and conf >= 0.45:     # §8.3 (be 0.5 / CONF 0.45)
        label = "Adapt concept"
    elif break_even >= 0.4:                                       # §8.3 (be 0.4)
        label = "Delay"
    else:
        label = "Do not launch"

    # Hard overrides — direct protection against bullshit (§8.3):
    if conf < 0.4:                       # see MODEL.md §8.3 — no Launch on unreliable data
        label = _cap_at(label, "Delay")
    if mape > 0.4:                       # see MODEL.md §8.3 — a weak backtest blocks Launch
        label = _cap_at(label, "Adapt concept")
    return label


def _decision_summary(label: str, break_even: float, risk_level: str, conf: float) -> str:
    """A short, number-grounded, business-agnostic summary line for decision.summary."""
    be_pct = round(break_even * 100)
    conf_pct = round(conf * 100)
    return (
        f"{label}: about {be_pct}% of months across the year clear break-even, "
        f"at {risk_level.lower()} risk and {conf_pct}% model confidence."
    )


# ===========================================================================
# §9 — Explanation (LLM over finished numbers, with a validator)
# ===========================================================================
_REASON_SYSTEM = (
    "You are a financial analyst explaining an ALREADY-MADE investment decision. "
    "Changing the numbers or the verdict is FORBIDDEN. "
    "Use ONLY the numbers from the input JSON — inventing new numbers, percentages, or amounts is FORBIDDEN. "
    "Every statement must reference a specific driver or number from the input. "
    "If there is no input data for a statement, do not make the statement. "
    "Return ONLY a single JSON object with keys: main_reason (string), "
    "positive_factors (string array), negative_factors (string array), recommended_actions (string array)."
)

_REASON_KEYS = {"main_reason", "positive_factors", "negative_factors", "recommended_actions"}


def _reason_payload(decision: dict, economics: dict, indices: dict, drivers: list[dict], key_assumptions: list[dict]) -> dict:
    """The ONLY thing the explanation LLM sees — finished numbers + categories (§9.1)."""
    return {
        "label": decision["label"],
        "score": decision["score"],
        "break_even_probability": economics["break_even_probability"],
        "payback_months": decision["_payback_months"],
        "payback_profile": indices["payback_profile"],
        "confidence": decision["confidence"],
        "risk_level": decision["risk_level"],
        "monthly_revenue": economics["expected_monthly_revenue_eur"],
        "monthly_profit": economics["expected_monthly_profit_eur"],
        "monthly_costs": economics["expected_monthly_costs_eur"],
        "downside_monthly_profit": economics["downside_monthly_profit_eur"],
        "upside_monthly_profit": economics["upside_monthly_profit_eur"],
        "roi": round(indices["ROI"], 2),
        "top_drivers": [{"name": d["name"], "direction": d.get("direction"), "importance": d.get("importance")} for d in drivers[:3]],
        "key_assumptions": key_assumptions,
        "seasonality_index": round(indices["SI"], 2),
        "investment_divergence": round(indices["divergence"], 2),
    }


def _collect_allowed_numbers(payload: dict) -> set[int]:
    """The set of integer-rounded numbers the LLM is allowed to mention (§9.3)."""
    allowed: set[int] = set(range(0, 101))  # small counts and percentages 0..100 are always fine
    allowed.update(range(0, 13))            # month counts

    def add(x: float) -> None:
        try:
            allowed.add(int(round(float(x))))
            allowed.add(int(round(float(x) * 100)))   # the percentage form of a fraction
        except (TypeError, ValueError):
            pass

    for key, value in payload.items():
        if isinstance(value, (int, float)):
            add(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, (int, float)):
                            add(v)
    return allowed


def _validate_reason(parsed: dict, payload: dict) -> bool:
    """Reject invented numbers and verdict mismatches (MODEL.md §9.3)."""
    if not isinstance(parsed, dict) or not _REASON_KEYS <= set(parsed):
        return False
    if not isinstance(parsed["main_reason"], str):
        return False
    for key in ("positive_factors", "negative_factors", "recommended_actions"):
        if not isinstance(parsed[key], list) or not all(isinstance(s, str) for s in parsed[key]):
            return False

    allowed = _collect_allowed_numbers(payload)
    text = " ".join([parsed["main_reason"], *parsed["positive_factors"], *parsed["negative_factors"], *parsed["recommended_actions"]])
    for token in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text):
        number = float(token.replace(",", ""))
        rounded = int(round(number))
        # Accept if within a ±1 rounding tolerance of any allowed number.
        if not any(abs(rounded - a) <= 1 for a in allowed):
            logger.warning("reason validation: invented number %s not in inputs → rejecting", token)
            return False
    return True


def _template_reason(payload: dict, drivers: list[dict]) -> dict:
    """Deterministic, number-grounded reason — the prod fallback and dev-free default (§9)."""
    be_pct = round(payload["break_even_probability"] * 100)
    positives = [d["name"] for d in drivers if d.get("direction") == "positive"][:2]
    negatives = [d["name"] for d in drivers if d.get("direction") == "negative"][:2]

    positive_factors = [f"Expected monthly profit of €{payload['monthly_profit']:,} on €{payload['monthly_revenue']:,} revenue."]
    if payload["upside_monthly_profit"] > payload["monthly_profit"]:
        positive_factors.append(f"In a strong month profit reaches €{payload['upside_monthly_profit']:,}.")
    positive_factors += [f"{name} supports demand." for name in positives]

    negative_factors = [f"Only {be_pct}% of months across the year clear break-even."]
    if payload["downside_monthly_profit"] < 0:
        negative_factors.append(f"A weak month falls to €{payload['downside_monthly_profit']:,} while fixed costs run year-round.")
    negative_factors += [f"{name} weighs on demand." for name in negatives]

    recommended_actions = [
        "Smooth seasonality with a complementary off-peak product line.",
        "Negotiate variable or turnover-linked fixed costs to cut downside risk.",
    ]
    if payload["risk_level"] == "High":
        recommended_actions.append("De-risk the highest-volatility driver before committing capital.")

    return {
        "main_reason": _decision_summary(payload["label"], payload["break_even_probability"], payload["risk_level"], payload["confidence"]),
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "recommended_actions": recommended_actions,
    }


def _llm_client():
    """A Featherless client if a key is configured, else None. Reuses translation_agent's client (no new HTTP client)."""
    try:
        from backend.translation_agent import FeatherlessClient  # lazy: keep report_agent light when LLM is unused
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not import FeatherlessClient (%s)", exc)
        return None
    client = FeatherlessClient()
    return client if client.available else None


def _parse_json_object(text: str) -> dict:
    """Extract a single JSON object from an LLM response (fences/prose tolerated)."""
    import json

    stripped = (text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(stripped[start : end + 1])


def build_reason(payload: dict, drivers: list[dict], *, mode: str, fallbacks: list[str]) -> dict:
    """STEP F — phrase the reason over the finished numbers (MODEL.md §9).

    Tries the LLM (strict prompt, one stricter retry, output validation). On any
    failure: prod → deterministic template + record the fallback; dev → raise.
    """
    import json

    client = _llm_client()
    if client is None:
        if mode == "dev":
            raise RuntimeError("LLM explanation unavailable and MODEL_MODE=dev")
        fallbacks.append("llm_explanation_unavailable->template")  # §1.1 loud fallback
        return _template_reason(payload, drivers)

    user_prompt = "Explain this decision using ONLY these numbers:\n" + json.dumps(payload)
    stricter = user_prompt + "\n\nReturn ONLY the JSON object. Do not introduce any number that is not in the input."
    for prompt in (user_prompt, stricter):
        try:
            parsed = _parse_json_object(client.chat(_REASON_SYSTEM, prompt, temperature=0.2, max_tokens=700))
            if parsed.get("label", payload["label"]) != payload["label"]:
                continue  # verdict mismatch (§9.3)
            if _validate_reason(parsed, payload):
                return {k: parsed[k] for k in _REASON_KEYS}
        except Exception as exc:  # noqa: BLE001
            logger.warning("reason LLM attempt failed: %s", exc)

    if mode == "dev":
        raise RuntimeError("LLM explanation failed validation and MODEL_MODE=dev")
    fallbacks.append("llm_explanation_invalid->template")  # §1.1 / §9.3 loud fallback
    return _template_reason(payload, drivers)


# ===========================================================================
# STEP A — Profiler (LLM)
# ===========================================================================
_PROFILER_SYSTEM = (
    "You are a business classifier. Project the described offline-retail business onto fixed axes. "
    "Return ONLY a single JSON object. Use ONLY these exact values per key:\n"
    + "\n".join(f"- {axis}: {values}" for axis, values in AXIS_VALUES.items())
    + "\nAlso include reasoning (string) and confidence (0..1). "
    "Output NO numbers for the axes — only the category labels above. "
    "You do NOT see any history, forecast, or money; classify from the description alone."
)


def profile_business(
    descriptions: list[str],
    user_input: str,
    *,
    mode: str,
    fallbacks: list[str],
) -> dict[str, Any]:
    """STEP A — classify the business onto the 8 axes (MODEL.md §3).

    The LLM emits categories only (never numbers). Out-of-enum values are coerced
    to the middle (§3.4). On an unavailable/failing LLM: prod → neutral profile +
    record fallback; dev → raise.
    """
    client = _llm_client()
    if client is None:
        if mode == "dev":
            raise RuntimeError("profiler LLM unavailable and MODEL_MODE=dev")
        fallbacks.append("profiler_unavailable->neutral_profile")  # §1.1 / §3.4 loud fallback
        return neutral_profile()

    text = "\n".join(["Business idea: " + user_input, "Factor descriptions:", *(f"- {d}" for d in descriptions)])
    stricter = text + "\n\nReturn ONLY the JSON object with the exact category values listed."
    for prompt in (text, stricter):
        try:
            raw = _parse_json_object(client.chat(_PROFILER_SYSTEM, prompt, temperature=0.1, max_tokens=400))
            return guard_profile(raw)  # enum guard never lets a bad value through (§3.4)
        except Exception as exc:  # noqa: BLE001
            logger.warning("profiler LLM attempt failed: %s", exc)

    if mode == "dev":
        raise RuntimeError("profiler LLM failed and MODEL_MODE=dev")
    fallbacks.append("profiler_unavailable->neutral_profile")  # §1.1 loud fallback
    return neutral_profile()


# ===========================================================================
# Graphs (ARCHITECTURE §5.6 shape)
# ===========================================================================
def build_graphs(timeseries: dict[str, float], forecast: list[dict], *, history_months: int = 18) -> dict:
    """Assemble the historical and forecast series in the result-contract shape."""
    items = sorted(timeseries.items())
    historical_series = [
        {"date": d, "historical": round(float(v), 2), "forecast": None, "low": None, "high": None}
        for d, v in items[-history_months:]
    ]
    demand_forecast = [
        {"date": p["date"], "historical": None, "forecast": p["forecast"], "low": p["low"], "high": p["high"]}
        for p in forecast
    ]
    return {"historical_series": historical_series, "demand_forecast": demand_forecast}


# ===========================================================================
# Result-contract models (ARCHITECTURE §5.6 + runtime) — enforce shape on the way out
# ===========================================================================
class _Decision(BaseModel):
    label: str
    score: int
    risk_level: str
    confidence: float
    summary: str


class _ExpectedRevenue(BaseModel):
    expected_monthly_revenue_eur: int
    expected_monthly_costs_eur: int
    expected_monthly_profit_eur: int
    downside_monthly_profit_eur: int
    upside_monthly_profit_eur: int
    break_even_probability: float
    payback_months: int | None


class _InvestmentItem(BaseModel):
    category: str
    amount: int


class _InvestmentCost(BaseModel):
    estimated_initial_investment_eur: int
    breakdown: list[_InvestmentItem]


class _GraphPoint(BaseModel):
    date: str
    historical: float | None = None
    forecast: float | None = None
    low: float | None = None
    high: float | None = None


class _Graphs(BaseModel):
    demand_forecast: list[_GraphPoint]
    historical_series: list[_GraphPoint]


class _Driver(BaseModel):
    name: str
    importance: float
    direction: str
    horizon: int | None = None


class _Backtest(BaseModel):
    mape: float
    rmse: float
    quality: str


class _Reason(BaseModel):
    main_reason: str
    positive_factors: list[str]
    negative_factors: list[str]
    recommended_actions: list[str]


class _Runtime(BaseModel):
    mode: str
    fallbacks: list[str]


class _Report(BaseModel):
    decision: _Decision
    expected_revenue: _ExpectedRevenue
    investment_cost: _InvestmentCost
    graphs: _Graphs
    drivers: list[_Driver]
    backtest: _Backtest
    reason: _Reason
    runtime: _Runtime


# ===========================================================================
# Context + assembler
# ===========================================================================
def _overrides_to_params(overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Map the frontend what-if override keys onto cascade ``user`` parameters."""
    params: dict[str, Any] = {}
    if not overrides:
        return params
    if overrides.get("monthly_rent_eur") is not None:
        params["rent"] = float(overrides["monthly_rent_eur"])
    if overrides.get("staff_costs_eur") is not None:
        params["staff"] = float(overrides["staff_costs_eur"])
    if overrides.get("other_fixed_eur") is not None:
        params["other"] = float(overrides["other_fixed_eur"])
    if overrides.get("average_basket_price_eur") is not None:
        params["basket"] = float(overrides["average_basket_price_eur"])
    if overrides.get("gross_margin_pct") is not None:
        params["margin"] = _clamp01(float(overrides["gross_margin_pct"]) / 100.0)
    if overrides.get("gross_margin") is not None:
        params["margin"] = _clamp01(float(overrides["gross_margin"]))
    if overrides.get("target_revenue_eur") is not None:
        params["target_revenue"] = float(overrides["target_revenue_eur"])
    if overrides.get("transactions_per_month") is not None:
        params["transactions"] = float(overrides["transactions_per_month"])
    return params


def _extract_user_params(user_input: str) -> dict[str, Any]:
    """Light, conservative extraction of explicit figures from the free-text idea (§5.7 tier 1).

    Only fires on clearly-marked amounts (e.g. "rent of €5000", "margin 60%"); the
    cascade falls back to table defaults otherwise — sparse input is not penalized.
    """
    params: dict[str, Any] = {}
    text = user_input or ""

    def money(after: str) -> float | None:
        m = re.search(after + r"[^\d€]{0,12}€?\s*([\d][\d,\.]*)\s*(k|000)?", text, re.IGNORECASE)
        if not m:
            return None
        value = float(m.group(1).replace(",", ""))
        if m.group(2):
            value *= 1000
        return value

    rent = money(r"rent")
    if rent is not None:
        params["rent"] = rent
    margin = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:gross\s*)?margin", text, re.IGNORECASE)
    if margin:
        params["margin"] = _clamp01(float(margin.group(1)) / 100.0)
    return params


@dataclass
class ReportContext:
    """Everything needed to (re)build a report without re-running the profiler/Sybilion."""

    timeseries: dict[str, float]
    metadata: dict[str, Any]
    forecast_bundle: dict
    profile: dict[str, Any]
    user_input: str = ""
    descriptions: list[str] = field(default_factory=list)
    user_params: dict[str, Any] = field(default_factory=dict)
    forecast_horizon_months: int = DEFAULT_HORIZON
    mode: str = "prod"
    prepare_fallbacks: list[str] = field(default_factory=list)
    seasonal: dict[int, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.seasonal:
            self.seasonal = seasonal_indices(self.timeseries)


def prepare_context(
    timeseries: dict[str, float],
    metadata: dict[str, Any] | None = None,
    user_input: str = "",
    descriptions: list[str] | None = None,
    *,
    forecast_horizon_months: int = DEFAULT_HORIZON,
    forecast_bundle: dict | None = None,
    business_profile: dict[str, Any] | None = None,
    mode: str | None = None,
) -> ReportContext:
    """Fetch the forecast once + run the profiler once, then bundle everything.

    The forecast and profile are cached on the context so ``recompute`` (what-if)
    never re-calls Sybilion or the profiler. Mode-aware fallbacks are recorded
    here (MODEL.md §1.1).
    """
    metadata = metadata or {}
    descriptions = descriptions or []
    mode = mode or _run_mode()
    horizon = max(HORIZON_MIN, min(HORIZON_MAX, int(forecast_horizon_months)))  # §2.2 clamp
    fallbacks: list[str] = []

    # Forecast (Sybilion) — record a loud fallback if it is synthetic (§1.1).
    bundle = forecast_bundle or sybilion_client.get_forecast(timeseries, metadata, forecast_horizon_months=horizon)
    if bundle.get("source") == "mock":
        if mode == "dev":
            raise RuntimeError("Sybilion unavailable (synthetic forecast) and MODEL_MODE=dev")
        fallbacks.append("sybilion_unavailable->synthetic_forecast")  # §1.1 loud fallback

    # Profiler (LLM) — inject a profile if provided (orchestrator/tests), else classify.
    if business_profile is not None:
        profile = guard_profile(business_profile)
    else:
        profile = profile_business(descriptions, user_input, mode=mode, fallbacks=fallbacks)

    user_params = _extract_user_params(user_input)
    return ReportContext(
        timeseries=timeseries,
        metadata=metadata,
        forecast_bundle=bundle,
        profile=profile,
        user_input=user_input,
        descriptions=descriptions,
        user_params=user_params,
        forecast_horizon_months=horizon,
        mode=mode,
        prepare_fallbacks=fallbacks,
    )


def assemble_report(context: ReportContext, overrides: dict[str, Any] | None = None) -> dict:
    """Run STEP B → STEP F deterministically and assemble the §5.6 report + runtime."""
    mode = context.mode
    fallbacks = list(context.prepare_fallbacks)  # prepare-time fallbacks (sybilion/profiler); reason may add more
    profile = context.profile
    seasonal = context.seasonal

    horizon = context.forecast_horizon_months
    forecast = context.forecast_bundle["forecast"][:horizon]   # honor the horizon (§2.2)
    drivers = context.forecast_bundle["drivers"]
    backtest = context.forecast_bundle["backtest"]
    mape = float(backtest.get("mape", 0.15))

    # STEP B — parameters (§5, §5.7)
    user_params = {**context.user_params, **_overrides_to_params(overrides)}
    params = resolve_parameters(profile, user_params)
    price = params["basket"].value
    margin = params["margin"].value
    fixed = params["rent"].value + params["staff"].value + params["other"].value  # §5.6
    sigma = _demand_sigma(profile)  # §5.4

    # STEP D — scale (§7.1) then economics (§7.2, §7.3)
    idx = [float(p["forecast"]) for p in forecast]
    months = [date.fromisoformat(p["date"]).month for p in forecast]
    mean_idx = sum(idx) / len(idx) if idx else 0.0
    seasonal_horizon = (sum(seasonal.get(m, 1.0) for m in months) / len(months)) if months else 1.0
    level_idx = mean_idx / (seasonal_horizon or 1.0)
    scale = resolve_scale(profile, user_params, level_idx, price, margin)
    economics = compute_economics(forecast, seasonal, scale.value, price, margin, fixed, sigma)

    # STEP D — investment (§7.4)
    monthly_revenue = economics["_monthly_revenue"]
    monthly_profit = economics["_monthly_profit"]
    investment = compute_investment(profile, monthly_revenue)
    inv_total = investment["estimated_initial_investment_eur"]

    # STEP C — indices (§6)
    si = seasonality_index(seasonal)                                    # §6.1
    ci = capital_intensity_index(inv_total, monthly_revenue)            # §6.2
    roi = roi_index(monthly_profit, inv_total)                         # §6.3
    pb = payback_index(inv_total, monthly_profit)                     # §6.4
    rel_band = forecast_band_width(forecast)                          # for §6.5 / §8.4
    conf = confidence_index(mape, len(context.timeseries), rel_band)  # §6.5
    conf_value = conf["CONF"]

    # STEP E — decision (§8)
    _, normal_payback, tolerable_payback = PAYBACK_PROFILE[profile["capital_intensity"]]  # §5.3
    risk = compute_risk(sigma, si, rel_band, investment["_divergence"])  # §8.4
    label = decision_label(
        economics["break_even_probability"], pb, (normal_payback, tolerable_payback),
        conf_value, risk["risk_level"], mape,
    )  # §8.3
    score = compute_score(economics["break_even_probability"], pb, tolerable_payback, roi, conf_value)  # §8.2
    payback_months = int(round(pb)) if math.isfinite(pb) and monthly_profit > 0 else None

    decision = {
        "label": label,
        "score": score,
        "risk_level": risk["risk_level"],
        "confidence": round(conf_value, 2),
        "summary": _decision_summary(label, economics["break_even_probability"], risk["risk_level"], conf_value),
        "_payback_months": payback_months,
    }

    # STEP F — reason (§9)
    key_assumptions = [
        {"param": "basket", "value": round(price, 2), "source": params["basket"].source},
        {"param": "margin", "value": round(margin, 2), "source": params["margin"].source},
        {"param": "rent", "value": round(params["rent"].value), "source": params["rent"].source},
        {"param": "staff", "value": round(params["staff"].value), "source": params["staff"].source},
        {"param": "scale", "value": round(scale.value, 2), "source": scale.source},
    ]
    indices = {
        "ROI": roi, "SI": si, "CI": ci, "divergence": investment["_divergence"],
        "payback_profile": f"{profile['capital_intensity']} (normal {normal_payback}, tolerable {tolerable_payback})",
    }
    payload = _reason_payload(decision, economics, indices, drivers, key_assumptions)
    reason = build_reason(payload, drivers, mode=mode, fallbacks=fallbacks)

    report = _Report(
        decision={k: v for k, v in decision.items() if not k.startswith("_")},
        expected_revenue={
            "expected_monthly_revenue_eur": economics["expected_monthly_revenue_eur"],
            "expected_monthly_costs_eur": economics["expected_monthly_costs_eur"],
            "expected_monthly_profit_eur": economics["expected_monthly_profit_eur"],
            "downside_monthly_profit_eur": economics["downside_monthly_profit_eur"],
            "upside_monthly_profit_eur": economics["upside_monthly_profit_eur"],
            "break_even_probability": economics["break_even_probability"],
            "payback_months": payback_months,
        },
        investment_cost={
            "estimated_initial_investment_eur": inv_total,
            "breakdown": investment["breakdown"],
        },
        graphs=build_graphs(context.timeseries, forecast),
        drivers=drivers,
        backtest=backtest,
        reason=reason,
        runtime={"mode": mode, "fallbacks": fallbacks},
    )
    result = report.model_dump()
    result["business_profile"] = {k: v for k, v in profile.items() if k != "reasoning"}
    result["parameters"] = {
        k: {"value": round(v.value, 4), "source": v.source}
        for k, v in params.items()
    }
    result["confidence_breakdown"] = {
        "c_forecast": round(conf["c_forecast"], 3),
        "c_data": round(conf["c_data"], 3),
        "c_band": round(conf["c_band"], 3),
        "confidence": round(conf_value, 3),
    }
    return result


def build_report(
    timeseries: dict[str, float],
    metadata: dict[str, Any] | None = None,
    user_input: str = "",
    descriptions: list[str] | None = None,
    *,
    forecast_horizon_months: int = DEFAULT_HORIZON,
    forecast_bundle: dict | None = None,
    business_profile: dict[str, Any] | None = None,
) -> dict:
    """End-to-end: profiler → params → indices → economics → decision → reason (§§3–9)."""
    context = prepare_context(
        timeseries, metadata, user_input, descriptions,
        forecast_horizon_months=forecast_horizon_months,
        forecast_bundle=forecast_bundle,
        business_profile=business_profile,
    )
    return assemble_report(context)


def recompute(context: ReportContext, overrides: dict[str, Any] | None) -> dict:
    """Fast what-if: re-derive params → economics → decision → reason for new inputs.

    Reuses the cached forecast AND the cached profile — no Sybilion call, no
    profiler call — so live demo tweaks update the verdict instantly (§3 of the task).
    """
    return assemble_report(context, overrides)


# ===========================================================================
# HTTP layer (standalone; the orchestrator can mount the router instead)
# ===========================================================================
router = APIRouter(tags=["report-agent"])


class ReportRequest(BaseModel):
    timeseries: dict[str, float]
    timeseries_metadata: dict[str, Any] = Field(default_factory=dict)
    userInput: str = ""
    descriptions: list[str] = Field(default_factory=list)
    forecast_horizon_months: int = DEFAULT_HORIZON
    business_profile: dict[str, Any] | None = None


class RecomputeRequest(ReportRequest):
    overrides: dict[str, Any] = Field(default_factory=dict)


@router.post("/report/build")
def post_build_report(request: ReportRequest) -> JSONResponse:
    try:
        report = build_report(
            request.timeseries, request.timeseries_metadata, request.userInput, request.descriptions,
            forecast_horizon_months=request.forecast_horizon_months,
            business_profile=request.business_profile,
        )
        return JSONResponse(content=report)
    except Exception as exc:  # clean structured error, never a raw 500 (dev surfaces it loudly via logs)
        logger.exception("build_report failed")
        return JSONResponse(status_code=500, content={"error": "report_failed", "detail": str(exc)})


@router.post("/report/recompute")
def post_recompute(request: RecomputeRequest) -> JSONResponse:
    """Fast what-if recompute, reusing the cached forecast (no Sybilion call)."""
    try:
        context = prepare_context(
            request.timeseries, request.timeseries_metadata, request.userInput, request.descriptions,
            forecast_horizon_months=request.forecast_horizon_months,
            business_profile=request.business_profile,
        )
        report = recompute(context, request.overrides)
        return JSONResponse(content=report)
    except Exception as exc:
        logger.exception("recompute failed")
        return JSONResponse(status_code=500, content={"error": "recompute_failed", "detail": str(exc)})


app = FastAPI(title="MarketPilot — Sybilion + Report Agent", version="2.0.0")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "report", "mode": _run_mode()}


# The canonical ice-cream show-case profile (MODEL.md §3): a tourist-district
# scoop shop — low ticket, high margin, strongly seasonal, perishable, and
# weather-sensitive. Used by the demo (and tests) so the numbers are deterministic
# without a live LLM call.
ICE_CREAM_PROFILE = {
    "capital_intensity": "medium",          # proper shop with freezers/seating in the 1st district
    "perishability": "high",                # ice cream melts
    "seasonality_expectation": "strong",
    "demand_breadth": "mixed",              # tourist + local, single weather-driven location
    "margin_class": "high",                 # high markup on inputs (§5.2)
    "ticket_class": "low",                  # ~€6 cone/cup (§5.1)
    "purchase_frequency": "periodic",
    "external_shock_sensitivity": "high",   # heatwaves / weather
    "reasoning": "Tourist-district ice cream shop: seasonal, perishable, weather-driven.",
    "confidence": 0.8,
}


if __name__ == "__main__":  # pragma: no cover - manual run
    import json

    from backend.data_engineer import _load_mock_timeseries

    demo = build_report(
        _load_mock_timeseries(),
        {"title": "Average Revenue of Icecream Shops in Vienna", "keywords": ["icecream", "weather", "seasons"]},
        "ice cream shop in Vienna's 1st district",
        business_profile=ICE_CREAM_PROFILE,
    )
    print(json.dumps(demo, indent=2))
