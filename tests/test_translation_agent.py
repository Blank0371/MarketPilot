"""Tests for the Block 3 Translation agent.

Run offline against the deterministic mock fallback (no FEATHERLESS_API_KEY), so
they exercise the contract shapes and the Data-Engineer hand-off without hitting
the network. The autouse fixture clears the env vars that would otherwise trigger
a real LLM / HTTP call.
"""

import pytest
from fastapi.testclient import TestClient

from backend import translation_agent
from backend.translation_agent import (
    STANDARDIZED_FACTORS,
    app,
    confirm_descriptions,
    descriptions_to_keywords,
    extract_descriptions,
)

client = TestClient(app)

ICE_CREAM_IDEA = "I want to open an ice cream shop in Vienna's 1st district."

# Each factor mapped to a substring that must appear somewhere in its rephrasing.
FACTOR_MARKERS = {
    "rent": "rent",
    "staff costs": "staff",
    "location foot traffic": "foot traffic",
    "average basket price": "basket",
    "margin": "margin",
    "seasonality": "season",
    "tourism dependency": "tourism",
}


@pytest.fixture(autouse=True)
def force_mock_path(monkeypatch):
    # No API key -> mock descriptions/keywords; no DATA_ENGINEER_URL -> in-process call.
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    monkeypatch.delenv("DATA_ENGINEER_URL", raising=False)


def test_extract_descriptions_includes_all_factors():
    descriptions = extract_descriptions(ICE_CREAM_IDEA)
    assert len(descriptions) == len(STANDARDIZED_FACTORS)
    blob = " ".join(descriptions).lower()
    for marker in FACTOR_MARKERS.values():
        assert marker in blob, f"missing factor marker: {marker!r}"
    # Rephrasing must localize to the user's input, not stay bare ("rent").
    assert "vienna" in blob


def test_extract_endpoint_contract_shape():
    response = client.post("/api/extract", json={"userInput": ICE_CREAM_IDEA})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"descriptions"}
    assert isinstance(body["descriptions"], list)
    assert all(isinstance(item, str) and item for item in body["descriptions"])


def test_extract_endpoint_rejects_empty_input():
    response = client.post("/api/extract", json={"userInput": ""})
    assert response.status_code == 422  # structured validation error, never a raw 500


def test_descriptions_to_keywords_returns_three_to_six():
    descriptions = extract_descriptions(ICE_CREAM_IDEA)
    keywords = descriptions_to_keywords(descriptions)
    assert 3 <= len(keywords) <= 6
    assert all(isinstance(keyword, str) and keyword for keyword in keywords)
    assert len(keywords) == len(set(keywords))  # deduped


def test_confirm_calls_data_engineer_with_right_shape(monkeypatch):
    captured = {}

    def fake_call(description, key_word):
        captured["description"] = description
        captured["key_word"] = key_word
        return {"timeseries_metadata": {"title": description}, "timeseries": {"2026-01-01": 1.0}}

    monkeypatch.setattr(translation_agent, "call_data_engineer", fake_call)

    descriptions = extract_descriptions(ICE_CREAM_IDEA)
    result = confirm_descriptions(descriptions)

    # Data-Engineer was called with a non-empty title and 3–6 keywords.
    assert isinstance(captured["description"], str) and captured["description"]
    assert 3 <= len(captured["key_word"]) <= 6
    # Response carries the Data-Engineer payload plus the transparent translation block.
    assert result["timeseries_metadata"]["title"] == captured["description"]
    assert set(result["translation"]) == {"keywords", "statistic_description"}
    assert result["translation"]["keywords"] == captured["key_word"]


def test_confirm_endpoint_returns_timeseries():
    # End-to-end through the in-process Data-Engineer (Block 2) fallback.
    descriptions = extract_descriptions(ICE_CREAM_IDEA)
    response = client.post("/api/confirm", json={"descriptions": descriptions})
    assert response.status_code == 200
    body = response.json()
    assert "timeseries_metadata" in body and "timeseries" in body
    assert len(body["timeseries"]) >= 60  # Block 2 serves the 60-point seasonal series
    assert 3 <= len(body["translation"]["keywords"]) <= 6
