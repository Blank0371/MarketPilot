"""Tests for the Block 4 report agent — v2.0 decision model (MODEL.md).

Migrated from the old (BASKETS_PER_INDEX_POINT / Monte-Carlo / one-dimensional
verdict) model to v2.0:

* the §5.6 contract shape + the new ``runtime`` block, and investment summing to
  its breakdown;
* the ice-cream show case reads as a non-trivial verdict ("Adapt concept");
* high rent flips the verdict down; a premium basket improves it;
* CONF (not the old ``confidence_from_backtest``) falls as MAPE rises;
* break-even is bounded by the downside/upside band;
* the economics are deterministic/reproducible and the break-even is analytical
  (no RNG/seed — the old subprocess-codegen path is gone, MODEL.md §11).

New v2.0 coverage: the profiler enum guard + neutral fallback, the forecast
horizon contract, the §8.3 CONF/MAPE Launch-block override, and prod
``runtime.fallbacks`` (+ the dev-mode loud failure).

Everything runs offline (no live LLM, no live Sybilion): the canonical
``ICE_CREAM_PROFILE`` is injected so the numbers are deterministic, and the
forecast comes from the cached mock artifacts.
"""

import copy

import pytest
from fastapi.testclient import TestClient

from backend.data_engineer import _load_mock_timeseries
from backend.report_agent import (
    ICE_CREAM_PROFILE,
    app,
    build_report,
    compute_economics,
    confidence_index,
    guard_profile,
    neutral_profile,
    prepare_context,
    profile_business,
    recompute,
    seasonal_indices,
    seasonality_index,
    _validate_reason,
)
from backend import sybilion_client

LABELS = {"Launch", "Adapt concept", "Delay", "Do not launch"}

TS = _load_mock_timeseries()
META = {"title": "Average Revenue of Icecream Shops in Vienna", "keywords": ["icecream", "weather", "seasons"]}


@pytest.fixture(autouse=True)
def _offline_prod_env(monkeypatch):
    """Force the deterministic offline path: no LLM, no live Sybilion, prod mode."""
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.delenv("SYBILION_API_TOKEN", raising=False)
    monkeypatch.setenv("MODEL_MODE", "prod")


def _baseline_report() -> dict:
    # Inject the ice-cream profile so the verdict is deterministic without a live LLM.
    return build_report(TS, META, "ice cream shop in Vienna's 1st district", business_profile=ICE_CREAM_PROFILE)


def _cache_bundle() -> dict:
    """A 'cache'-source forecast bundle (real-ish data → no Sybilion fallback)."""
    bundle = dict(sybilion_client.get_forecast(TS, use_live=False, forecast_horizon_months=6))
    bundle["source"] = "cache"
    return bundle


# ---------------------------------------------------------------------------
# Contract shape (+ runtime + investment invariant)
# ---------------------------------------------------------------------------
def test_report_matches_contract_shape():
    r = _baseline_report()
    assert set(r) == {"decision", "expected_revenue", "investment_cost", "graphs", "drivers", "backtest", "reason", "runtime"}

    d = r["decision"]
    assert set(d) == {"label", "score", "risk_level", "confidence", "summary"}
    assert d["label"] in LABELS
    assert 0 <= d["score"] <= 100
    assert 0.0 <= d["confidence"] <= 1.0

    e = r["expected_revenue"]
    assert set(e) == {
        "expected_monthly_revenue_eur", "expected_monthly_costs_eur", "expected_monthly_profit_eur",
        "downside_monthly_profit_eur", "upside_monthly_profit_eur", "break_even_probability", "payback_months",
    }

    # Investment MUST sum to its breakdown (a hard contract invariant).
    inv = r["investment_cost"]
    assert inv["estimated_initial_investment_eur"] == sum(item["amount"] for item in inv["breakdown"])

    # Graphs: history carries `historical`; the forecast carries forecast + band.
    assert r["graphs"]["historical_series"][0]["historical"] is not None
    first_fc = r["graphs"]["demand_forecast"][0]
    assert first_fc["forecast"] is not None and first_fc["low"] is not None and first_fc["high"] is not None

    # Drivers include `horizon` so the UI can show how importance shifts over months.
    assert any("horizon" in driver for driver in r["drivers"])

    assert set(r["backtest"]) == {"mape", "rmse", "quality"}
    assert set(r["reason"]) == {"main_reason", "positive_factors", "negative_factors", "recommended_actions"}

    # New v2.0 runtime block (MODEL.md §1.1).
    assert set(r["runtime"]) == {"mode", "fallbacks"}
    assert r["runtime"]["mode"] == "prod"
    assert isinstance(r["runtime"]["fallbacks"], list)


def test_baseline_is_adapt_concept():
    """The ice-cream show case reads as a non-trivial 'Adapt concept'.

    Under v2.0 this is a MULTI-DIMENSIONAL verdict (MODEL.md §8.3): break-even
    (~0.65) and payback (~18 mo) are actually healthy, but the verdict is held at
    "Adapt concept" by the HIGH risk dimension — strong seasonality (SI≈0.88),
    perishability, and weather sensitivity. That is exactly the intended story
    ("strong summer demand, but winter seasonality creates downside risk").

    Note on the §7.3 sanity figure: the spec illustrates break-even ≈ 0.55–0.60,
    but the spec-faithful number on the real demo series is ~0.65 because the
    cached forecast carries YoY growth (~+4.7%), lifting the de-seasonalized level
    above the historical mean. The LABEL is unchanged ("Adapt concept"); only the
    mechanism shifted from a borderline break-even to the risk dimension — a
    stronger demonstration of the multi-dimensional decision, so we assert the
    label and keep break-even in a tolerant band.
    """
    r = _baseline_report()
    assert r["decision"]["label"] == "Adapt concept"
    assert r["decision"]["risk_level"] == "High"
    assert 0.5 <= r["expected_revenue"]["break_even_probability"] < 0.75


def test_high_rent_lowers_profit_and_flips_verdict():
    ctx = prepare_context(TS, META, business_profile=ICE_CREAM_PROFILE)
    base = recompute(ctx, None)
    high = recompute(ctx, {"monthly_rent_eur": 11000})
    assert high["expected_revenue"]["expected_monthly_profit_eur"] < base["expected_revenue"]["expected_monthly_profit_eur"]
    assert high["expected_revenue"]["break_even_probability"] < base["expected_revenue"]["break_even_probability"]
    assert high["decision"]["label"] in {"Delay", "Do not launch"}
    assert high["decision"]["label"] != base["decision"]["label"]


def test_recompute_premium_basket_improves_verdict():
    """Higher basket → better economics → better verdict (direction, MODEL.md §8.2).

    The exact label may stay "Adapt concept" rather than reaching "Launch": for a
    strongly seasonal/perishable/weather-driven business the risk dimension is
    structurally HIGH and blocks Launch regardless of price (§8.3, §8.4). So we
    assert the *improvement* (profit, break-even, and score all rise), per the
    v2.0 migration note.
    """
    ctx = prepare_context(TS, META, business_profile=ICE_CREAM_PROFILE)
    base = recompute(ctx, None)
    premium = recompute(ctx, {"average_basket_price_eur": 9.0})
    assert premium["expected_revenue"]["expected_monthly_profit_eur"] > base["expected_revenue"]["expected_monthly_profit_eur"]
    assert premium["expected_revenue"]["break_even_probability"] >= base["expected_revenue"]["break_even_probability"]
    assert premium["decision"]["score"] > base["decision"]["score"]


def test_bad_backtest_lowers_confidence():
    """CONF (MODEL.md §6.5) replaces the old two-magic-number confidence_from_backtest."""
    good = confidence_index(mape=0.05, history_len=60, rel_band_width=0.25)["CONF"]
    bad = confidence_index(mape=0.35, history_len=60, rel_band_width=0.25)["CONF"]
    assert good > bad
    assert 0.0 <= bad <= good <= 1.0
    # History sufficiency also drives CONF: less history → lower (c_data, §6.5).
    short = confidence_index(mape=0.05, history_len=12, rel_band_width=0.25)["CONF"]
    assert short < good


def test_break_even_uses_the_band():
    e = _baseline_report()["expected_revenue"]
    assert e["downside_monthly_profit_eur"] < e["expected_monthly_profit_eur"] < e["upside_monthly_profit_eur"]
    assert 0.0 <= e["break_even_probability"] <= 1.0


def test_economics_are_analytical_and_reproducible():
    """Replaces the retired subprocess-codegen / _validate_executed tests (MODEL.md §11).

    The economics are pure deterministic Python: no RNG, no seed, no subprocess.
    Identical inputs MUST yield byte-identical numbers, and the break-even is the
    analytical normal-CDF value (§7.3), so two calls agree exactly.
    """
    forecast = sybilion_client.get_forecast(TS, use_live=False)["forecast"]
    seasonal = seasonal_indices(TS)
    # scale=30, price=6, margin=0.70, fixed=17400, sigma=0.24 (ice-cream defaults)
    args = (forecast, seasonal, 30.0, 6.0, 0.70, 17400.0, 0.24)
    first = compute_economics(*args)
    second = compute_economics(*args)
    assert first == second
    assert 0.0 <= first["break_even_probability"] <= 1.0

    # The whole report is reproducible too (no hidden randomness).
    assert build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE) == build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE)


# ---------------------------------------------------------------------------
# New v2.0 behaviour
# ---------------------------------------------------------------------------
def test_profiler_enum_guard_and_neutral_fallback():
    # Out-of-enum values are coerced to the documented middle (MODEL.md §3.4).
    guarded = guard_profile({"capital_intensity": "banana", "margin_class": "high", "ticket_class": "WUT", "confidence": "x"})
    assert guarded["capital_intensity"] == "medium"   # bad → middle
    assert guarded["ticket_class"] == "medium"        # bad → middle
    assert guarded["margin_class"] == "high"          # valid → kept
    assert 0.0 <= guarded["confidence"] <= 1.0

    # With no LLM available, prod returns the neutral profile AND records the fallback (§3.4 / §1.1).
    fallbacks: list[str] = []
    profile = profile_business([], "", mode="prod", fallbacks=fallbacks)
    assert profile == neutral_profile() or all(profile[a] for a in ("capital_intensity", "margin_class"))
    assert "profiler_unavailable->neutral_profile" in fallbacks


def test_forecast_horizon_is_honored_and_clamped():
    # The horizon bounds how many forecast points drive the report (MODEL.md §2.2).
    r3 = build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_horizon_months=3)
    r6 = build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_horizon_months=6)
    assert len(r3["graphs"]["demand_forecast"]) == 3
    assert len(r6["graphs"]["demand_forecast"]) == 6
    # A 3-month (peak-only) horizon estimates a different demand level than 6 months.
    assert r3["expected_revenue"]["expected_monthly_revenue_eur"] != r6["expected_revenue"]["expected_monthly_revenue_eur"]

    # Out-of-range values are clamped to [1, 12], never raising in prod.
    r_hi = build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_horizon_months=99)
    assert len(r_hi["graphs"]["demand_forecast"]) == 12
    r_lo = build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_horizon_months=0)
    assert len(r_lo["graphs"]["demand_forecast"]) == 1


def test_low_conf_or_high_mape_cannot_launch():
    """A weak backtest (high MAPE / low CONF) must block 'Launch' (MODEL.md §8.3 override)."""
    low_risk = {
        "capital_intensity": "medium", "perishability": "none", "seasonality_expectation": "moderate",
        "demand_breadth": "mass", "margin_class": "high", "ticket_class": "low",
        "purchase_frequency": "daily", "external_shock_sensitivity": "low",
    }
    good = _cache_bundle()  # mape ≈ 0.10 → would Launch with a strong basket
    ctx_good = prepare_context(TS, META, "x", business_profile=low_risk, forecast_bundle=good)
    assert recompute(ctx_good, {"average_basket_price_eur": 10.0})["decision"]["label"] == "Launch"

    bad = copy.deepcopy(good)
    bad["backtest"] = {"mape": 0.45, "rmse": 100.0, "quality": "low"}  # MAPE > 0.4
    ctx_bad = prepare_context(TS, META, "x", business_profile=low_risk, forecast_bundle=bad)
    knocked = recompute(ctx_bad, {"average_basket_price_eur": 10.0})
    assert knocked["decision"]["label"] != "Launch"


def test_runtime_fallbacks_populated_in_prod():
    # A synthetic ("mock") forecast in prod is recorded loudly (MODEL.md §1.1).
    mock_bundle = dict(sybilion_client.get_forecast(TS, use_live=False))
    mock_bundle["source"] = "mock"
    r = build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_bundle=mock_bundle)
    assert "sybilion_unavailable->synthetic_forecast" in r["runtime"]["fallbacks"]


def test_dev_mode_raises_instead_of_falling_back(monkeypatch):
    # In dev there are NO silent fallbacks: an unavailable profiler LLM raises (§1.1, P6).
    monkeypatch.setenv("MODEL_MODE", "dev")
    cache = _cache_bundle()
    with pytest.raises(RuntimeError):
        build_report(TS, META, "x", forecast_bundle=cache)  # no injected profile, no LLM key → raise

    # A synthetic forecast also raises in dev.
    mock_bundle = dict(cache)
    mock_bundle["source"] = "mock"
    with pytest.raises(RuntimeError):
        build_report(TS, META, "x", business_profile=ICE_CREAM_PROFILE, forecast_bundle=mock_bundle)


def test_reason_validator_rejects_invented_numbers():
    """The explanation validator catches numbers not present in the input (MODEL.md §9.3)."""
    payload = {"label": "Adapt concept", "break_even_probability": 0.65, "monthly_profit": 3884, "monthly_revenue": 30405}
    grounded = {
        "main_reason": "Adapt concept: about 65% of months clear break-even.",
        "positive_factors": ["Monthly profit of 3884 on revenue of 30405."],
        "negative_factors": [], "recommended_actions": [],
    }
    invented = {
        "main_reason": "This will easily clear 99999 in monthly profit.",
        "positive_factors": [], "negative_factors": [], "recommended_actions": [],
    }
    assert _validate_reason(grounded, payload) is True
    assert _validate_reason(invented, payload) is False


def test_seasonality_index_reflects_amplitude():
    si = seasonality_index(seasonal_indices(TS))
    assert 0.5 < si < 1.5  # ice cream is strongly (but not extremely) seasonal


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
def test_http_build_and_recompute():
    client = TestClient(app)
    body = {
        "timeseries": TS, "timeseries_metadata": META, "userInput": "ice cream shop",
        "business_profile": ICE_CREAM_PROFILE,
    }
    built = client.post("/report/build", json=body)
    assert built.status_code == 200
    payload = built.json()
    assert payload["decision"]["label"] in LABELS
    assert payload["runtime"]["mode"] == "prod"

    recomputed = client.post("/report/recompute", json={**body, "overrides": {"monthly_rent_eur": 11000}})
    assert recomputed.status_code == 200
    assert recomputed.json()["decision"]["label"] in {"Delay", "Do not launch"}
