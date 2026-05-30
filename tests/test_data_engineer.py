"""Tests for the Block 2 Data-Engineer agent.

Covers the contract shape, the 60-point first-of-month series, the seasonal
shape (summer > winter), and the keyWord alias + enrichment.
"""

from datetime import date

from fastapi.testclient import TestClient

from backend.data_engineer import (
    app,
    generate_icecream_series,
    get_timeseries,
    validate_timeseries,
)

client = TestClient(app)

SUMMER = {"06", "07", "08"}
WINTER = {"12", "01", "02"}


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
