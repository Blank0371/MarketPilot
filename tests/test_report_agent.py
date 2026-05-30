"""Tests for the Block 4 report agent.

Covers the ARCHITECTURE.md §5.6 contract shape, the executed-Python economics
(validated against the in-process truth), the deterministic verdict (high rent
flips it, premium basket lifts it, bad backtest lowers confidence), break-even
from the band, and the fast what-if recompute.
"""

from fastapi.testclient import TestClient

from backend.data_engineer import _load_mock_timeseries
from backend.report_agent import (
    Assumptions,
    app,
    build_report,
    compute_economics,
    confidence_from_backtest,
    prepare_context,
    recompute,
    seasonal_indices,
    _economics_inproc,
    _validate_executed,
)
from backend.sybilion_client import get_forecast

LABELS = {"Launch", "Adapt concept", "Delay", "Do not launch"}

TS = _load_mock_timeseries()
META = {"title": "Average Revenue of Icecream Shops in Vienna", "keywords": ["icecream", "weather", "seasons"]}


def _baseline_report() -> dict:
    return build_report(TS, META, "ice cream shop in Vienna's 1st district")


def test_report_matches_contract_shape():
    r = _baseline_report()
    assert set(r) == {"decision", "expected_revenue", "investment_cost", "graphs", "drivers", "backtest", "reason"}

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


def test_baseline_is_adapt_concept():
    # The show case must read as "Adapt concept" (consistent with ARCHITECTURE §5.6).
    assert _baseline_report()["decision"]["label"] == "Adapt concept"


def test_high_rent_lowers_profit_and_flips_verdict():
    ctx = prepare_context(TS, META)
    base = recompute(ctx, None)
    high = recompute(ctx, {"monthly_rent_eur": 11000})
    assert high["expected_revenue"]["expected_monthly_profit_eur"] < base["expected_revenue"]["expected_monthly_profit_eur"]
    assert high["expected_revenue"]["break_even_probability"] < base["expected_revenue"]["break_even_probability"]
    assert high["decision"]["label"] in {"Delay", "Do not launch"}
    assert high["decision"]["label"] != base["decision"]["label"]


def test_recompute_premium_basket_improves_verdict():
    ctx = prepare_context(TS, META)
    base = recompute(ctx, None)
    premium = recompute(ctx, {"average_basket_price_eur": 9.0})
    assert premium["expected_revenue"]["expected_monthly_profit_eur"] > base["expected_revenue"]["expected_monthly_profit_eur"]
    assert premium["decision"]["label"] == "Launch"


def test_bad_backtest_lowers_confidence():
    good = confidence_from_backtest({"mape": 0.05})
    bad = confidence_from_backtest({"mape": 0.35})
    assert good > bad
    assert 0.0 <= bad <= good <= 1.0


def test_break_even_uses_the_band():
    e = _baseline_report()["expected_revenue"]
    assert e["downside_monthly_profit_eur"] < e["expected_monthly_profit_eur"] < e["upside_monthly_profit_eur"]
    assert 0.0 <= e["break_even_probability"] <= 1.0


def test_economics_come_from_executed_python_and_validate():
    forecast = get_forecast(TS, use_live=False)["forecast"]
    seasonal = seasonal_indices(TS)
    economics = compute_economics(forecast, seasonal, Assumptions())
    assert economics["_computation_source"] in {"executed_python_script", "deterministic_inprocess"}

    # The validator accepts matching numbers and rejects an invented profit.
    trusted = _economics_inproc(forecast, seasonal, Assumptions())
    assert _validate_executed(trusted, trusted) is True
    bogus = {**trusted, "expected_monthly_profit_eur": trusted["expected_monthly_profit_eur"] + 10000}
    assert _validate_executed(bogus, trusted) is False


def test_recompute_is_deterministic_with_codegen_disabled(monkeypatch):
    # With codegen off the in-process calc runs and is fully reproducible.
    monkeypatch.setenv("REPORT_DISABLE_CODEGEN", "1")
    ctx = prepare_context(TS, META)
    first = recompute(ctx, {"gross_margin_pct": 50})
    second = recompute(ctx, {"gross_margin_pct": 50})
    assert first["expected_revenue"] == second["expected_revenue"]
    assert first["decision"]["label"] == "Do not launch"  # thin margin kills the year


def test_http_build_and_recompute():
    client = TestClient(app)
    body = {"timeseries": TS, "timeseries_metadata": META, "userInput": "ice cream shop"}
    built = client.post("/report/build", json=body)
    assert built.status_code == 200
    assert built.json()["decision"]["label"] in LABELS

    recomputed = client.post("/report/recompute", json={**body, "overrides": {"monthly_rent_eur": 11000}})
    assert recomputed.status_code == 200
    assert recomputed.json()["decision"]["label"] in {"Delay", "Do not launch"}
