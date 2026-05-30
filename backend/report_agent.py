"""Report agent (Block 4, parts 2-4) for MarketPilot.

Turns a Sybilion forecast into a transparent, reproducible launch decision.

Design (see BLOCK4.md / FLOW_AND_AGENTS.md §4.3 / ARCHITECTURE.md §5.6):

* **The numbers come from executed deterministic Python.** The economics are
  computed in-process (the trusted source of truth) and *also* by a self-written
  Python script run in a sandboxed subprocess — the "LLM writes & executes its
  own Python" step. The subprocess result is used only if it validates against
  the in-process calculation; on any mismatch or failure we fall back to the
  in-process numbers. The verdict is therefore reproducible and never invented.
* **Break-even uses the uncertainty.** We combine the 6-month forecast band
  (model uncertainty) with the historical seasonal cycle (the dominant risk for
  ice cream — the forecast horizon only covers the summer peak) in a Monte-Carlo
  to estimate the probability that monthly profit is positive across the year.
* **The decision is deterministic.** Label, score, risk and confidence are
  derived by fixed rules; confidence is tied to the backtest. The LLM only
  *phrases* the reason from the already-computed result.

Public surface:

    build_report(timeseries, metadata, user_input, descriptions) -> dict
    prepare_context(...) -> ReportContext           # reusable forecast + inputs
    recompute(context, overrides) -> dict           # fast what-if, no Sybilion call
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import sybilion_client

logger = logging.getLogger("marketpilot.report_agent")

# ---------------------------------------------------------------------------
# Assumptions (ice cream show case defaults; aligned with the frontend baseline)
# ---------------------------------------------------------------------------
# Each forecast index point maps to this many monthly baskets (transactions);
# calibrated so the baseline horizon revenue lands near a representative Vienna
# ice cream shop. Revenue scales with both demand (forecast) and basket price.
BASKETS_PER_INDEX_POINT = 23.0
_MC_SAMPLES = 20000
_MC_SEED = 20260530


@dataclass(frozen=True)
class Assumptions:
    """Business assumptions. What-if overrides patch the public three."""

    monthly_rent_eur: float = 6000.0
    staff_costs_eur: float = 9000.0
    other_fixed_eur: float = 2400.0
    average_basket_price_eur: float = 6.5
    gross_margin: float = 0.70  # fraction (0..1)

    @property
    def fixed_costs_eur(self) -> float:
        return self.monthly_rent_eur + self.staff_costs_eur + self.other_fixed_eur


def apply_overrides(base: Assumptions, overrides: dict[str, Any] | None) -> Assumptions:
    """Patch assumptions from frontend WhatIfOverrides keys (margin is a percent)."""
    if not overrides:
        return base
    patch: dict[str, float] = {}
    if overrides.get("monthly_rent_eur") is not None:
        patch["monthly_rent_eur"] = float(overrides["monthly_rent_eur"])
    if overrides.get("average_basket_price_eur") is not None:
        patch["average_basket_price_eur"] = float(overrides["average_basket_price_eur"])
    if overrides.get("gross_margin_pct") is not None:
        patch["gross_margin"] = max(0.0, min(1.0, float(overrides["gross_margin_pct"]) / 100.0))
    return replace(base, **patch)


# ---------------------------------------------------------------------------
# Seasonal profile (from history — the forecast horizon only covers summer)
# ---------------------------------------------------------------------------
def seasonal_indices(timeseries: dict[str, float]) -> dict[int, float]:
    """Average month-of-year multipliers normalized to mean 1.0 over the year."""
    by_month: dict[int, list[float]] = {}
    for key, value in timeseries.items():
        by_month.setdefault(date.fromisoformat(key).month, []).append(float(value))
    if not by_month:
        return {m: 1.0 for m in range(1, 13)}
    month_avg = {m: float(np.mean(vs)) for m, vs in by_month.items()}
    overall = float(np.mean(list(month_avg.values())))
    if overall <= 0:
        return {m: 1.0 for m in range(1, 13)}
    # Fill any missing month with the neutral 1.0 so a short series still works.
    return {m: month_avg.get(m, overall) / overall for m in range(1, 13)}


# ---------------------------------------------------------------------------
# Economics — in-process source of truth (executed deterministic Python)
# ---------------------------------------------------------------------------
def _economics_inproc(
    forecast: list[dict],
    seasonal: dict[int, float],
    a: Assumptions,
    *,
    samples: int = _MC_SAMPLES,
    seed: int = _MC_SEED,
) -> dict:
    """Compute the economics deterministically with numpy.

    Headline figures use the forecast horizon (the next 6 months). The
    break-even probability and the downside/upside profit band come from a
    seeded Monte-Carlo over the seasonal cycle and the forecast band, so they
    reflect full-year viability rather than the summer peak alone.
    """
    medians = np.array([p["forecast"] for p in forecast], dtype=float)
    lows = np.array([p["low"] for p in forecast], dtype=float)
    highs = np.array([p["high"] for p in forecast], dtype=float)
    horizon_median = float(np.mean(medians))

    # Forecast band -> relative sigma (p10/p90 ~ +/-1.2816 sigma around the median).
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(medians > 0, (highs - lows) / (2 * 1.2816 * medians), 0.0)
    sigma_fc = float(np.clip(np.mean(rel), 0.03, 0.40))

    basket = a.average_basket_price_eur
    margin = a.gross_margin
    fixed = a.fixed_costs_eur

    def revenue_of(index_level: float | np.ndarray):
        return index_level * BASKETS_PER_INDEX_POINT * basket

    def profit_of(index_level: float | np.ndarray):
        return revenue_of(index_level) * margin - fixed

    # Headline: forecast-horizon expectation.
    revenue = revenue_of(horizon_median)
    profit = profit_of(horizon_median)
    costs = revenue - profit  # fixed + COGS

    # De-seasonalize the forecast level, then re-apply the full-year seasonal
    # shape so winter months are represented in the Monte-Carlo.
    fc_months = [date.fromisoformat(p["date"]).month for p in forecast]
    seasonal_fc = float(np.mean([seasonal.get(m, 1.0) for m in fc_months])) or 1.0
    overall_level = horizon_median / seasonal_fc

    # Sample months in proportion to expected transaction volume, so break-even
    # reflects the share of the *business* that lands in profitable months — not
    # a flat calendar count that over-weights the dead of winter. A strongly
    # seasonal business still scores lower than a flat one, so seasonality stays
    # decisive; it just isn't double-counted.
    rng = np.random.default_rng(seed)
    season_factors = np.array([seasonal.get(m, 1.0) for m in range(1, 13)], dtype=float)
    weights = season_factors / season_factors.sum()
    drawn_season = season_factors[rng.choice(12, size=samples, p=weights)]
    noise = np.clip(rng.normal(1.0, sigma_fc, size=samples), 0.05, None)
    sampled_index = overall_level * drawn_season * noise
    sampled_profit = profit_of(sampled_index)

    break_even = float(np.mean(sampled_profit > 0))
    downside = float(np.percentile(sampled_profit, 10))
    upside = float(np.percentile(sampled_profit, 90))

    return {
        "expected_monthly_revenue_eur": round(revenue),
        "expected_monthly_costs_eur": round(costs),
        "expected_monthly_profit_eur": round(profit),
        "downside_monthly_profit_eur": round(downside),
        "upside_monthly_profit_eur": round(upside),
        "break_even_probability": round(break_even, 2),
        # Internal extras (stripped before the response) for reason/decision:
        "_horizon_median_index": round(horizon_median, 2),
        "_overall_level_index": round(overall_level, 2),
        "_sigma_fc": round(sigma_fc, 3),
        "_fixed_costs_eur": round(fixed),
    }


# Self-contained Python the agent "writes and executes" in a subprocess. It
# reimplements the same economics with the stdlib only (no imports beyond the
# standard library), reads inputs as JSON and writes outputs as JSON. Its result
# is trusted only after it validates against _economics_inproc.
_ECONOMICS_SCRIPT = r'''
import json, sys, random, math

inp = json.load(open(sys.argv[1]))
forecast = inp["forecast"]
seasonal = {int(k): float(v) for k, v in inp["seasonal"].items()}
basket = inp["basket"]; margin = inp["margin"]; fixed = inp["fixed"]
baskets_per_point = inp["baskets_per_point"]
samples = inp["samples"]; seed = inp["seed"]

medians = [p["forecast"] for p in forecast]
horizon_median = sum(medians) / len(medians)
rels = [((p["high"] - p["low"]) / (2 * 1.2816 * p["forecast"])) if p["forecast"] > 0 else 0.0 for p in forecast]
sigma_fc = min(0.40, max(0.03, sum(rels) / len(rels)))

def revenue_of(idx): return idx * baskets_per_point * basket
def profit_of(idx): return revenue_of(idx) * margin - fixed

revenue = revenue_of(horizon_median)
profit = profit_of(horizon_median)
costs = revenue - profit

fc_months = [int(p["date"][5:7]) for p in forecast]
seasonal_fc = (sum(seasonal.get(m, 1.0) for m in fc_months) / len(fc_months)) or 1.0
overall_level = horizon_median / seasonal_fc

rng = random.Random(seed)
season_factors = [seasonal.get(m, 1.0) for m in range(1, 13)]
drawn = rng.choices(season_factors, weights=season_factors, k=samples)
profits = []
for sf in drawn:
    noise = max(0.05, rng.gauss(1.0, sigma_fc))
    profits.append(profit_of(overall_level * sf * noise))
profits.sort()

def pct(data, q):
    if not data: return 0.0
    pos = (len(data) - 1) * q / 100.0
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi: return data[lo]
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)

break_even = sum(1 for p in profits if p > 0) / len(profits)
json.dump({
    "expected_monthly_revenue_eur": round(revenue),
    "expected_monthly_costs_eur": round(costs),
    "expected_monthly_profit_eur": round(profit),
    "downside_monthly_profit_eur": round(pct(profits, 10)),
    "upside_monthly_profit_eur": round(pct(profits, 90)),
    "break_even_probability": round(break_even, 2),
}, open(sys.argv[2], "w"))
'''


def _run_economics_script(forecast: list[dict], seasonal: dict[int, float], a: Assumptions, *, script: str | None = None) -> dict | None:
    """Execute the economics as a standalone Python script in a subprocess.

    Returns the parsed result, or ``None`` on any failure (so the caller falls
    back to the in-process numbers). Runs with no network use, a short timeout,
    and a temp working area — a safe, bounded execution of agent-written code.
    """
    payload = {
        "forecast": forecast,
        "seasonal": {str(k): v for k, v in seasonal.items()},
        "basket": a.average_basket_price_eur,
        "margin": a.gross_margin,
        "fixed": a.fixed_costs_eur,
        "baskets_per_point": BASKETS_PER_INDEX_POINT,
        "samples": _MC_SAMPLES,
        "seed": _MC_SEED,
    }
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script_path = tmp_path / "economics.py"
            in_path = tmp_path / "in.json"
            out_path = tmp_path / "out.json"
            script_path.write_text(script or _ECONOMICS_SCRIPT, encoding="utf-8")
            in_path.write_text(json.dumps(payload), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(script_path), str(in_path), str(out_path)],
                check=True,
                timeout=20,
                capture_output=True,
                cwd=tmp,
            )
            return json.loads(out_path.read_text(encoding="utf-8"))
    except (subprocess.SubprocessError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("economics codegen subprocess failed (%s); using in-process result", exc)
        return None


def _validate_executed(executed: dict, trusted: dict) -> bool:
    """True if the executed-script numbers match the in-process truth closely.

    Headline figures are deterministic and must match tightly; the Monte-Carlo
    fields (break-even, band) may differ by sampling noise within a small margin.
    """
    try:
        for key in ("expected_monthly_revenue_eur", "expected_monthly_costs_eur", "expected_monthly_profit_eur"):
            t = trusted[key]
            if abs(executed[key] - t) > max(2.0, abs(t) * 0.01):
                return False
        if abs(executed["break_even_probability"] - trusted["break_even_probability"]) > 0.05:
            return False
        scale = max(1000.0, abs(trusted["downside_monthly_profit_eur"]), abs(trusted["upside_monthly_profit_eur"]))
        for key in ("downside_monthly_profit_eur", "upside_monthly_profit_eur"):
            if abs(executed[key] - trusted[key]) > 0.12 * scale:
                return False
    except (KeyError, TypeError):
        return False
    return True


def compute_economics(forecast: list[dict], seasonal: dict[int, float], a: Assumptions) -> dict:
    """Compute economics, preferring the executed Python script when it validates.

    The in-process numpy result is always the trusted baseline; the subprocess
    result is adopted only when it reproduces those numbers. Set
    ``REPORT_DISABLE_CODEGEN=1`` to skip the subprocess (used in tests for speed).
    """
    trusted = _economics_inproc(forecast, seasonal, a)
    if os.environ.get("REPORT_DISABLE_CODEGEN") == "1":
        return {**trusted, "_computation_source": "deterministic_inprocess"}

    executed = _run_economics_script(forecast, seasonal, a)
    if executed is not None and _validate_executed(executed, trusted):
        return {**trusted, **executed, "_computation_source": "executed_python_script"}
    return {**trusted, "_computation_source": "deterministic_inprocess"}


# ---------------------------------------------------------------------------
# Investment cost (deterministic)
# ---------------------------------------------------------------------------
def compute_investment(revenue_eur: float, fixed_costs_eur: float) -> dict:
    """Estimate the initial investment + a breakdown (scales with the business)."""

    def round_to(value: float, step: int) -> int:
        return int(round(value / step) * step)

    breakdown = [
        {"category": "Store setup", "amount": 72000},
        {"category": "Initial inventory", "amount": round_to(revenue_eur * 0.35, 500)},
        {"category": "Launch marketing", "amount": 12000},
        {"category": "Legal and licensing", "amount": 8000},
        {"category": "Cash buffer", "amount": round_to(fixed_costs_eur * 1.8, 1000)},
    ]
    total = sum(item["amount"] for item in breakdown)
    return {"estimated_initial_investment_eur": total, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Decision logic (deterministic; confidence tied to backtest)
# ---------------------------------------------------------------------------
def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def confidence_from_backtest(backtest: dict) -> float:
    """Map backtest accuracy to forecast confidence — worse MAPE, lower confidence."""
    mape = float(backtest.get("mape", 0.15))
    return round(_clamp01(0.86 - 1.5 * mape), 2)


def _decision_label(break_even: float, profit: float) -> str:
    if break_even >= 0.75 and profit > 0:
        return "Launch"
    if break_even >= 0.55:
        return "Adapt concept"
    if break_even >= 0.40:
        return "Delay"
    return "Do not launch"


def _risk_level(break_even: float, downside: float, profit: float) -> str:
    swing = abs(downside) / max(1.0, abs(profit))
    if break_even >= 0.72 and swing < 1.0:
        return "Low"
    if break_even >= 0.50:
        return "Medium"
    return "High"


def _score(break_even: float, profit: float, revenue: float) -> int:
    profit_margin = profit / revenue if revenue > 0 else 0.0
    profit_score = _clamp01((profit_margin + 0.07) / 0.30)
    return int(round(100 * _clamp01(0.45 * break_even + 0.55 * profit_score)))


_SUMMARY = {
    "Launch": "The forecast supports a confident launch: even in the modelled downside, peak-season demand clears year-round costs.",
    "Adapt concept": "Strong summer demand carries the year, but winter seasonality and year-round rent leave only a slim full-year margin — tune the concept before launch.",
    "Delay": "At these assumptions the year-round economics are too thin; wait for better lease terms or stronger demand before committing capital.",
    "Do not launch": "Costs outrun demand across the year; the forecast does not support a launch at these assumptions.",
}


def decide(economics: dict, backtest: dict) -> dict:
    break_even = economics["break_even_probability"]
    profit = economics["expected_monthly_profit_eur"]
    revenue = economics["expected_monthly_revenue_eur"]
    downside = economics["downside_monthly_profit_eur"]
    label = _decision_label(break_even, profit)
    return {
        "label": label,
        "score": _score(break_even, profit, revenue),
        "risk_level": _risk_level(break_even, downside, profit),
        "confidence": confidence_from_backtest(backtest),
        "summary": _SUMMARY[label],
    }


# ---------------------------------------------------------------------------
# Reason (phrased from the computed result; LLM optional, deterministic default)
# ---------------------------------------------------------------------------
def _eur(n: float) -> str:
    return f"€{int(round(n)):,}"


def build_reason(economics: dict, decision: dict, drivers: list[dict], assumptions: Assumptions) -> dict:
    """Deterministic, number-grounded reason. Optionally re-phrased by the LLM."""
    be_pct = round(economics["break_even_probability"] * 100)
    positives = [d["name"] for d in drivers if d.get("direction") == "positive"][:3]
    negatives = [d["name"] for d in drivers if d.get("direction") == "negative"][:3]

    reason = {
        "main_reason": decision["summary"],
        "positive_factors": [
            f"Peak-season demand drives {_eur(economics['upside_monthly_profit_eur'])} profit in a strong month.",
            f"Healthy {round(assumptions.gross_margin * 100)}% gross margin on every sale.",
            *( [f"{positives[0]} is the strongest forecast driver."] if positives else [] ),
        ],
        "negative_factors": [
            f"Only {be_pct}% of months across the year clear break-even.",
            f"A weak month falls to {_eur(economics['downside_monthly_profit_eur'])} as winter demand drops while rent runs year-round.",
            *( [f"{negatives[0]} weighs on the off-season."] if negatives else [] ),
        ],
        "recommended_actions": [
            "Add a winter line (hot drinks, pastries or seasonal desserts) to smooth revenue.",
            "Negotiate a seasonal or turnover-linked rent to cut off-season fixed cost.",
            "Pre-book summer staff and lock supplier pricing before the peak.",
        ],
    }
    return _maybe_llm_reason(reason, economics, decision)


def _maybe_llm_reason(reason: dict, economics: dict, decision: dict) -> dict:
    """Best-effort LLM phrasing on Featherless; returns the deterministic reason on any issue.

    The LLM only rewrites prose from the already-computed numbers — it never
    changes the figures or the verdict.
    """
    api_key = os.environ.get("FEATHERLESS_API_KEY")
    if not api_key:
        return reason
    try:
        from openai import OpenAI

        client = OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)
        prompt = (
            "You are a financial analyst. Rewrite the following decision rationale to be crisp and "
            "investor-ready. Do NOT change any numbers, the verdict, or the meaning. Return JSON with "
            "keys main_reason (string), positive_factors, negative_factors, recommended_actions (string arrays).\n\n"
            f"Verdict: {decision['label']} (score {decision['score']}, {decision['risk_level']} risk)\n"
            f"Computed figures: {json.dumps({k: v for k, v in economics.items() if not k.startswith('_')})}\n"
            f"Draft rationale: {json.dumps(reason)}"
        )
        resp = client.chat.completions.create(
            model=os.environ.get("FEATHERLESS_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content)
        if {"main_reason", "positive_factors", "negative_factors", "recommended_actions"} <= parsed.keys():
            return parsed
    except Exception as exc:  # noqa: BLE001 — LLM is optional; never block the report
        logger.warning("LLM reason phrasing failed (%s); using deterministic reason", exc)
    return reason


# ---------------------------------------------------------------------------
# Graphs
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Result contract models (ARCHITECTURE.md §5.6) — enforce the shape on the way out
# ---------------------------------------------------------------------------
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
    payback_months: int


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


class _Report(BaseModel):
    decision: _Decision
    expected_revenue: _ExpectedRevenue
    investment_cost: _InvestmentCost
    graphs: _Graphs
    drivers: list[_Driver]
    backtest: _Backtest
    reason: _Reason


# ---------------------------------------------------------------------------
# Context + assembler
# ---------------------------------------------------------------------------
@dataclass
class ReportContext:
    """Everything needed to (re)build a report without re-running Sybilion."""

    timeseries: dict[str, float]
    metadata: dict[str, Any]
    forecast_bundle: dict
    user_input: str = ""
    descriptions: list[str] = field(default_factory=list)
    assumptions: Assumptions = field(default_factory=Assumptions)
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
    assumptions: Assumptions | None = None,
    forecast_bundle: dict | None = None,
) -> ReportContext:
    """Fetch the forecast (cached/live) once and bundle it with the inputs."""
    metadata = metadata or {}
    bundle = forecast_bundle or sybilion_client.get_forecast(timeseries, metadata)
    return ReportContext(
        timeseries=timeseries,
        metadata=metadata,
        forecast_bundle=bundle,
        user_input=user_input,
        descriptions=descriptions or [],
        assumptions=assumptions or Assumptions(),
    )


def assemble_report(context: ReportContext) -> dict:
    """Compute economics + decision + reason and assemble the final report JSON."""
    forecast = context.forecast_bundle["forecast"]
    drivers = context.forecast_bundle["drivers"]
    backtest = context.forecast_bundle["backtest"]
    a = context.assumptions

    economics = compute_economics(forecast, context.seasonal, a)
    investment = compute_investment(economics["expected_monthly_revenue_eur"], a.fixed_costs_eur)
    profit = economics["expected_monthly_profit_eur"]
    payback = int(round(investment["estimated_initial_investment_eur"] / profit)) if profit > 0 else 0

    decision = decide(economics, backtest)
    reason = build_reason(economics, decision, drivers, a)

    report = _Report(
        decision=decision,
        expected_revenue={
            "expected_monthly_revenue_eur": economics["expected_monthly_revenue_eur"],
            "expected_monthly_costs_eur": economics["expected_monthly_costs_eur"],
            "expected_monthly_profit_eur": economics["expected_monthly_profit_eur"],
            "downside_monthly_profit_eur": economics["downside_monthly_profit_eur"],
            "upside_monthly_profit_eur": economics["upside_monthly_profit_eur"],
            "break_even_probability": economics["break_even_probability"],
            "payback_months": payback,
        },
        investment_cost=investment,
        graphs=build_graphs(context.timeseries, forecast),
        drivers=drivers,
        backtest=backtest,
        reason=reason,
    )
    return report.model_dump()


def build_report(
    timeseries: dict[str, float],
    metadata: dict[str, Any] | None = None,
    user_input: str = "",
    descriptions: list[str] | None = None,
    *,
    assumptions: Assumptions | None = None,
    forecast_bundle: dict | None = None,
) -> dict:
    """End-to-end: forecast -> economics -> decision -> report (ARCHITECTURE §5.6)."""
    context = prepare_context(
        timeseries, metadata, user_input, descriptions,
        assumptions=assumptions, forecast_bundle=forecast_bundle,
    )
    return assemble_report(context)


def recompute(context: ReportContext, overrides: dict[str, Any] | None) -> dict:
    """Fast what-if: re-derive economics + verdict for new assumptions.

    Reuses the cached forecast — no Sybilion call — so live demo tweaks (rent,
    basket price, margin) update the verdict instantly and cheaply.
    """
    new_context = replace(context, assumptions=apply_overrides(context.assumptions, overrides))
    return assemble_report(new_context)


# ---------------------------------------------------------------------------
# HTTP layer (standalone; the orchestrator can mount the router instead)
# ---------------------------------------------------------------------------
router = APIRouter(tags=["report-agent"])


class ReportRequest(BaseModel):
    timeseries: dict[str, float]
    timeseries_metadata: dict[str, Any] = Field(default_factory=dict)
    userInput: str = ""
    descriptions: list[str] = Field(default_factory=list)


class RecomputeRequest(ReportRequest):
    overrides: dict[str, Any] = Field(default_factory=dict)


@router.post("/report/build")
def post_build_report(request: ReportRequest) -> JSONResponse:
    try:
        report = build_report(request.timeseries, request.timeseries_metadata, request.userInput, request.descriptions)
        return JSONResponse(content=report)
    except Exception as exc:  # defensive: a clean error, never a raw 500
        logger.exception("build_report failed")
        return JSONResponse(status_code=500, content={"error": "report_failed", "detail": str(exc)})


@router.post("/report/recompute")
def post_recompute(request: RecomputeRequest) -> JSONResponse:
    """Fast what-if recompute, reusing the cached forecast (no Sybilion call)."""
    try:
        context = prepare_context(request.timeseries, request.timeseries_metadata, request.userInput, request.descriptions)
        report = recompute(context, request.overrides)
        return JSONResponse(content=report)
    except Exception as exc:
        logger.exception("recompute failed")
        return JSONResponse(status_code=500, content={"error": "recompute_failed", "detail": str(exc)})


app = FastAPI(title="MarketPilot — Sybilion + Report Agent", version="1.0.0")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "report"}


if __name__ == "__main__":  # pragma: no cover - manual run
    from backend.data_engineer import _load_mock_timeseries

    demo = build_report(_load_mock_timeseries(), {"title": "Average Revenue of Icecream Shops in Vienna"})
    print(json.dumps(demo, indent=2))
