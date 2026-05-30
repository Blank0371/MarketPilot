"""Tests for the Block 4 Sybilion client.

Covers the request shape, the normalized fallback result, quantile parsing
(0.1/0.5/0.9 — not p10/p50), and the deterministic mock-artifact generation.
"""

from datetime import date

from backend.data_engineer import _load_mock_timeseries
from backend.sybilion_client import (
    build_forecast_request,
    generate_mock_artifacts,
    get_forecast,
    parse_forecast_artifact,
    quality_from_mape,
)


def test_build_request_matches_sybilion_shape():
    ts = {"2021-12-01": 218.5, "2022-01-01": 148.1}
    meta = {"title": "Ice cream Vienna", "description": "desc", "keywords": ["icecream", "weather"]}
    body = build_forecast_request(ts, meta)
    assert body["pipeline_version"] == "v1"
    assert body["frequency"] == "monthly"
    assert body["soft_horizon"] == 6
    assert 0 <= body["recency_factor"] <= 1
    assert body["timeseries_metadata"]["keywords"] == ["icecream", "weather"]
    assert body["timeseries"]["2021-12-01"] == 218.5


def test_get_forecast_falls_back_to_cache_without_token():
    # No SYBILION_API_TOKEN in the test env -> normalized cache/mock result.
    result = get_forecast(_load_mock_timeseries(), use_live=False)
    assert result["source"] in {"cache", "mock"}
    assert len(result["forecast"]) == 6
    for point in result["forecast"]:
        assert set(point) == {"date", "forecast", "low", "high"}
        assert point["low"] <= point["forecast"] <= point["high"]
        assert date.fromisoformat(point["date"]).day == 1
    # Drivers + backtest are surfaced for the dashboard.
    assert result["drivers"] and "importance" in result["drivers"][0]
    assert {"mape", "rmse", "quality"} <= set(result["backtest"])


def test_parse_forecast_reads_quantile_keys():
    raw = {
        "data": {
            "forecast_series": {
                "2026-06-01": {"forecast": 78.4, "quantile_forecast": {"0.1": 68.2, "0.5": 78.4, "0.9": 89.1}},
            }
        }
    }
    parsed = parse_forecast_artifact(raw)
    assert parsed == [{"date": "2026-06-01", "forecast": 78.4, "low": 68.2, "high": 89.1}]


def test_generate_mock_artifacts_projects_future_first_of_month():
    ts = _load_mock_timeseries()
    artifacts = generate_mock_artifacts(ts)
    series = artifacts["forecast"]["data"]["forecast_series"]
    assert len(series) == 6
    last_history = max(date.fromisoformat(k) for k in ts)
    for key, point in series.items():
        d = date.fromisoformat(key)
        assert d.day == 1 and d > last_history  # forecast is after the history
        q = point["quantile_forecast"]
        assert q["0.1"] <= q["0.5"] <= q["0.9"]


def test_quality_from_mape_thresholds():
    assert quality_from_mape(0.05) == "high"
    assert quality_from_mape(0.12) == "medium-high"
    assert quality_from_mape(0.20) == "medium"
    assert quality_from_mape(0.40) == "low"
