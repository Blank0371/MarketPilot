"""Tests for the Block 2 Data-Engineer agent.

Covers the contract shape, the 60-point first-of-month series, the seasonal
shape (summer > winter), and the keyWord alias + enrichment.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.data_engineer import (
    SeriesResolution,
    _adapt_query_response_to_monthly_series,
    _keyword_classify_description,
    _to_month_start,
    _validate_llm_routing,
    app,
    generate_icecream_series,
    get_timeseries,
    resolve_series,
    validate_timeseries,
)

client = TestClient(app)

SUMMER = {"06", "07", "08"}
WINTER = {"12", "01", "02"}


@pytest.fixture(autouse=True)
def _force_offline_routing(monkeypatch):
    # Keep DE tests hermetic and deterministic: never hit live LLM routing,
    # regardless of whether FEATHERLESS_API_KEY is set in the local environment.
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)


def _avg(values: list[float]) -> float:
    return sum(values) / len(values)


def test_endpoint_returns_contract_shape():
    response = client.post(
        "/data/timeseries",
        json={"description": "Average Revenue of Icecreamshops in Vienna with filter", "keyWord": ["icecream", "weather"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"timeseries_metadata", "timeseries"}

    metadata = body["timeseries_metadata"]
    assert set(metadata) == {"title", "description", "keywords"}
    assert metadata["title"] == "Average Revenue of Icecreamshops in Vienna with filter"
    assert isinstance(body["timeseries"], dict)
    assert all(isinstance(value, (int, float)) for value in body["timeseries"].values())


def test_series_has_60_first_of_month_points():
    series = get_timeseries("Average Revenue of Icecreamshops in Vienna", ["icecream"])["timeseries"]
    assert len(series) >= 60
    for key in series:
        # Keys must be YYYY-MM-DD on the first of the month, or Sybilion rejects them.
        assert date.fromisoformat(key).day == 1


def test_summer_exceeds_winter_seasonality():
    series = get_timeseries("Ice cream demand", [])["timeseries"]
    summer = [value for key, value in series.items() if key[5:7] in SUMMER]
    winter = [value for key, value in series.items() if key[5:7] in WINTER]
    assert summer and winter
    assert _avg(summer) > _avg(winter)


def test_keyword_alias_and_enrichment():
    # The contract field is camelCase `keyWord`; enrichment adds generic demand terms.
    body = client.post("/data/timeseries", json={"description": "Foot traffic", "keyWord": ["icecream"]}).json()
    keywords = body["timeseries_metadata"]["keywords"]
    assert "icecream" in keywords
    assert "seasons" in keywords and "weather" in keywords


def test_empty_description_is_rejected_cleanly():
    response = client.post("/data/timeseries", json={"description": "", "keyWord": []})
    assert response.status_code == 422  # structured validation error, never a raw 500


def test_generated_mock_passes_validation():
    diagnostics = validate_timeseries(generate_icecream_series(), today=date(2026, 5, 30))
    assert diagnostics == []


# ---------------------------------------------------------------------------
# v2 — atomic data-request routing
# ---------------------------------------------------------------------------
def test_rent_description_maps_to_rent():
    assert _keyword_classify_description("monthly rent for a 1,500 sq ft retail space") == "rent"


def test_staff_description_maps_to_staff_costs():
    assert _keyword_classify_description(
        "average hourly wage for 2-3 full-time staff plus benefits"
    ) == "staff costs"


def test_foot_traffic_description_maps_to_location_foot_traffic():
    assert _keyword_classify_description(
        "daily pedestrian count near the proposed storefront"
    ) == "location foot traffic"


def test_average_transaction_maps_to_average_basket_price():
    assert _keyword_classify_description(
        "average transaction value for wine purchases in the local market"
    ) == "average basket price"


def test_margin_description_maps_to_margin():
    assert _keyword_classify_description("typical profit margin on wine sales") == "margin"


def test_holidays_description_maps_to_seasonality():
    assert _keyword_classify_description(
        "monthly fluctuations in wine sales due to holidays and events"
    ) == "seasonality"


def test_tourist_description_maps_to_tourism_dependency():
    assert _keyword_classify_description(
        "percentage of sales attributed to tourists in the area"
    ) == "tourism dependency"


def test_unrelated_description_is_unsupported():
    assert _keyword_classify_description("local regulations and bureaucratic paperwork") == "unsupported"


def test_no_llm_key_fallback_still_returns_monthly_series():
    # autouse fixture removed the key — this must still yield a healthy series.
    # today is pinned to the data window (like test_generated_mock_passes_validation)
    # so the check doesn't depend on the wall clock.
    series = get_timeseries("monthly rent for a retail unit", [])["timeseries"]
    assert len(series) >= 60
    assert validate_timeseries(series, today=date(2026, 5, 30)) == []


def test_output_keys_are_month_start_dates():
    series = get_timeseries("typical profit margin on sales", [])["timeseries"]
    assert series and all(date.fromisoformat(key).day == 1 for key in series)


def test_output_values_are_float():
    series = get_timeseries("daily pedestrian count near storefront", [])["timeseries"]
    assert series and all(isinstance(value, float) for value in series.values())


def test_resolve_series_reports_category_and_keeps_contract():
    resolution = resolve_series("monthly rent for a 1,500 sq ft retail space", [])
    assert isinstance(resolution, SeriesResolution)
    assert resolution.category == "rent"
    assert resolution.source_id == "mock_rent_retail"
    assert resolution.source_quality == "mock"
    assert len(resolution.monthly_series) >= 60


def test_get_timeseries_is_deterministic():
    a = get_timeseries("monthly rent for a 1,500 sq ft retail space", [])["timeseries"]
    b = get_timeseries("monthly rent for a 1,500 sq ft retail space", [])["timeseries"]
    assert a == b


def test_different_categories_yield_different_series():
    # Acceptance #1: no longer the same hardcoded history for every description.
    rent = get_timeseries("monthly rent for a retail unit", [])["timeseries"]
    margin = get_timeseries("typical gross margin on sales", [])["timeseries"]
    foot = get_timeseries("daily pedestrian count near storefront", [])["timeseries"]
    assert list(rent.values()) != list(margin.values())
    assert list(rent.values()) != list(foot.values())


def test_quarterly_dates_expand_to_months():
    assert _to_month_start("2024-Q1") == ["2024-01-01", "2024-02-01", "2024-03-01"]


def test_yearly_date_expands_to_twelve_months():
    months = _to_month_start("2024")
    assert len(months) == 12
    assert months[0] == "2024-01-01" and months[-1] == "2024-12-01"


def test_month_and_day_tokens_normalise_to_month_start():
    assert _to_month_start("2024-01") == ["2024-01-01"]
    assert _to_month_start("2024-01-17") == ["2024-01-01"]


def test_unknown_llm_source_id_is_rejected():
    routing = _validate_llm_routing({
        "category": "rent",
        "source_id": "totally_made_up_source",
        "source_quality": "exact",
        "reason": "x",
    })
    assert routing is not None
    assert routing["source_id"] is None        # invented id dropped
    assert routing["source_quality"] == "mock"  # downgraded — no real source exists


def test_unsupported_llm_category_is_rejected():
    # Macro indicators the model must not substitute for demand are refused,
    # forcing the deterministic keyword fallback.
    assert _validate_llm_routing({
        "category": "inflation_index", "source_id": None,
        "source_quality": "none", "reason": "macro",
    }) is None


def test_adapter_normalises_query_response_to_monthly():
    response = {"data": [
        {"date": "2024-01-15", "value": 10.0},
        {"date": "2024-01-28", "value": 20.0},   # same month -> averaged
        {"date": "2024-Q2", "value": 5.0},        # quarter -> 3 months
        {"date": "2023", "value": 1.0},           # year -> 12 months
    ]}
    series = _adapt_query_response_to_monthly_series(response)
    assert series["2024-01-01"] == 15.0          # (10 + 20) / 2
    assert series["2024-04-01"] == 5.0 and series["2024-06-01"] == 5.0
    assert series["2023-01-01"] == 1.0 and series["2023-12-01"] == 1.0
    assert all(date.fromisoformat(key).day == 1 for key in series)


# ---------------------------------------------------------------------------
# v2 — revenue-title routing (wired pipeline passes a composite revenue title)
# ---------------------------------------------------------------------------
def test_revenue_title_routes_to_generic_not_factor_generator():
    # A factor word in the idea name must NOT hijack the revenue title to a
    # factor generator (e.g. 'staffing' -> staff costs ~7800 EUR payroll).
    for title in (
        "Average revenue of staffing agency in Vienna",
        "Average revenue of seasonal pop-up in Vienna",
        "Average revenue of tourist souvenir shop in Vienna",
    ):
        assert _keyword_classify_description(title) == "unsupported"
        resolution = resolve_series(title, [])
        assert resolution.category == "revenue"
        # Generic revenue magnitude (~110-215), not payroll/index/percent units.
        assert all(50.0 < value < 400.0 for value in resolution.monthly_series.values())


def test_revenue_title_keeps_seasonal_revenue_shape():
    # The ice-cream demo title must still yield a healthy seasonal revenue series.
    series = get_timeseries("Average revenue of ice cream shops in Vienna", [])["timeseries"]
    assert len(series) >= 60
    assert validate_timeseries(series, today=date(2026, 5, 30)) == []
    summer = [value for key, value in series.items() if key[5:7] in SUMMER]
    winter = [value for key, value in series.items() if key[5:7] in WINTER]
    assert _avg(summer) > _avg(winter)


def test_sales_in_atomic_description_is_not_a_revenue_cue():
    # 'sales' is NOT a revenue cue: atomic factor descriptions that contain it
    # must still route to their factor category, not the generic revenue series.
    assert _keyword_classify_description(
        "monthly fluctuations in wine sales due to holidays and events"
    ) == "seasonality"
    assert _keyword_classify_description(
        "typical profit margin on wine sales in the region"
    ) == "margin"
