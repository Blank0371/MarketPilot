"""Data-Engineer agent (Block 2) for MarketPilot.

Given a description + keywords, returns a historical monthly time series with
metadata. For now it serves realistic mock data for an ice cream shop in Vienna;
the source-registry stub (§ "Future: real sources") shows where live data
fetching plugs in later.

Contract (canonical — see FLOW_AND_AGENTS.md §4.2):

    POST /data/timeseries
    request : { "description": str, "keyWord": [str, ...] }
    response: { "timeseries_metadata": { "title", "description", "keywords" },
                "timeseries": { "YYYY-MM-DD": float, ... } }

The same logic is exposed as ``get_timeseries(description, key_word)`` so the
orchestrator can import and call it directly without HTTP.
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("marketpilot.data_engineer")

# Path to the committed mock series (repo_root/mock/timeseries_icecream.json).
MOCK_PATH = Path(__file__).resolve().parent.parent / "mock" / "timeseries_icecream.json"

# Keywords we always add so the forecast picks up demand drivers even when the
# caller forgot them. Enrichment is intentionally generic (works for any retail
# business), not ice-cream-specific.
ENRICHMENT_KEYWORDS: tuple[str, ...] = ("seasons", "weather")

# Mock-series generation parameters. Tuned so summer clearly beats winter and
# the series satisfies Sybilion's 60-point minimum for a 4–6 month horizon.
_SERIES_MONTHS = 60
_SERIES_LAST_MONTH = date(2026, 4, 1)  # most recent obs, within the past 12 months
_SERIES_BASE = 130.0  # starting revenue index
_SERIES_TREND_PER_MONTH = 0.6  # mild upward drift
_SERIES_SEASONAL_AMPLITUDE = 0.45  # +/-45% swing → strong, visible seasonality
_SERIES_NOISE = 3.0  # +/- month-to-month jitter so it looks real
_SERIES_SEED = 20260530  # fixed seed → deterministic file & stable tests


# ---------------------------------------------------------------------------
# Wire models (match the contract field names exactly)
# ---------------------------------------------------------------------------
class TimeseriesRequest(BaseModel):
    """Incoming request. Note the camelCase ``keyWord`` from the source of truth."""

    model_config = ConfigDict(populate_by_name=True)

    description: str = Field(..., min_length=1)
    key_word: list[str] = Field(default_factory=list, alias="keyWord")


class TimeseriesMetadata(BaseModel):
    title: str
    description: str
    keywords: list[str]


class TimeseriesResponse(BaseModel):
    timeseries_metadata: TimeseriesMetadata
    timeseries: dict[str, float]


# ---------------------------------------------------------------------------
# Future: real sources (stub — keep the shape, don't wire live calls yet)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    """An approved data source the agent may query once live fetching lands."""

    name: str
    description: str
    api_schema: dict = field(default_factory=dict)


# Registry of approved sources. Descriptions/schemas are illustrative; they
# document *how* each source would be queried for the last 60 monthly points.
APPROVED_SOURCES: list[Source] = [
    Source(
        "FRED",
        "US Federal Reserve Economic Data — macro & financial monthly series.",
        {"base_url": "https://api.stlouisfed.org/fred", "query": ["series_id", "frequency=m", "observation_start"]},
    ),
    Source(
        "Eurostat",
        "EU statistics — regional retail turnover, tourism nights, consumer prices.",
        {"base_url": "https://ec.europa.eu/eurostat/api/dissemination", "query": ["dataset", "geo", "freq=M"]},
    ),
    Source(
        "World Bank",
        "Global development indicators (often annual — resample to monthly).",
        {"base_url": "https://api.worldbank.org/v2", "query": ["country", "indicator", "format=json"]},
    ),
    Source(
        "Yahoo Finance",
        "Market prices for tickers (commodities, FX, equities).",
        {"base_url": "https://query1.finance.yahoo.com/v8/finance/chart", "query": ["symbol", "interval=1mo", "range=5y"]},
    ),
    Source(
        "Our World in Data",
        "Curated global datasets (energy, climate, demographics).",
        {"base_url": "https://ourworldindata.org/grapher", "query": ["slug", "csv"]},
    ),
]


def select_source(description: str, key_word: list[str]) -> Source | None:
    """Pick the best-fitting approved source for this request.

    Returns ``None`` for now so ``get_timeseries`` falls back to the mock.
    """
    # TODO: real source selection — score each APPROVED_SOURCES entry against the
    # description/keywords (embedding or keyword overlap), choose the best match,
    # build its API request, fetch the last 60 monthly observations, and
    # normalize into the standard response shape. Until then we serve the mock.
    return None


# ---------------------------------------------------------------------------
# Mock series
# ---------------------------------------------------------------------------
def _first_of_month_back(last: date, n: int) -> list[date]:
    """Return ``n`` ascending first-of-month dates ending at ``last`` (inclusive)."""
    months: list[date] = []
    year, month = last.year, last.month
    for _ in range(n):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def generate_icecream_series(
    n_months: int = _SERIES_MONTHS,
    last_month: date = _SERIES_LAST_MONTH,
) -> dict[str, float]:
    """Deterministically generate a seasonal ice-cream revenue series.

    Summer (Jun–Aug) peaks, winter (Dec–Feb) troughs, a mild upward trend, and
    small month-to-month noise so it reads as real data. Same seed every call,
    so the committed mock file and the tests stay in sync.
    """
    rng = random.Random(_SERIES_SEED)
    series: dict[str, float] = {}
    for i, day in enumerate(_first_of_month_back(last_month, n_months)):
        trend = _SERIES_BASE + _SERIES_TREND_PER_MONTH * i
        # cos peaks at month 7 (July) and troughs at month 1 (January).
        seasonal = 1.0 + _SERIES_SEASONAL_AMPLITUDE * math.cos(2 * math.pi * (day.month - 7) / 12)
        noise = rng.uniform(-_SERIES_NOISE, _SERIES_NOISE)
        series[day.isoformat()] = round(trend * seasonal + noise, 1)
    return series


def _load_mock_timeseries() -> dict[str, float]:
    """Load the committed mock series; regenerate in memory if the file is gone."""
    try:
        with MOCK_PATH.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        raw = payload.get("timeseries", payload)
        series = {str(k): float(v) for k, v in raw.items()}
        if not series:
            raise ValueError("mock series is empty")
        return series
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("mock file unavailable at %s (%s); regenerating in memory", MOCK_PATH, exc)
        return generate_icecream_series()


# ---------------------------------------------------------------------------
# Validation helpers (matter when real data arrives; mock always passes)
# ---------------------------------------------------------------------------
def _parse_month_key(key: str) -> date:
    """Parse a ``YYYY-MM-DD`` key, raising if it is not the first of the month."""
    parsed = date.fromisoformat(key)
    if parsed.day != 1:
        raise ValueError(f"key {key!r} is not the first day of the month")
    return parsed


def validate_timeseries(
    series: dict[str, float],
    *,
    min_points: int = 60,
    max_gap_months: int = 2,
    recency_months: int = 12,
    today: date | None = None,
) -> list[str]:
    """Return a list of diagnostic strings — empty means the series looks healthy.

    Checks: first-of-month keys, monthly frequency without long gaps, the
    minimum point count, and that the most recent observation is recent enough
    for Sybilion (within the past 12 months).
    """
    diagnostics: list[str] = []
    if not series:
        return ["series is empty"]

    months: list[date] = []
    for key in series:
        try:
            months.append(_parse_month_key(key))
        except ValueError as exc:
            diagnostics.append(str(exc))
    if not months:
        return diagnostics or ["no valid month keys"]
    months.sort()

    if len(series) < min_points:
        diagnostics.append(f"only {len(series)} points; Sybilion needs >= {min_points} for a 4–6 month horizon")

    for earlier, later in zip(months, months[1:]):
        gap = (later.year - earlier.year) * 12 + (later.month - earlier.month)
        if gap > max_gap_months:
            diagnostics.append(f"gap of {gap} months between {earlier.isoformat()} and {later.isoformat()}")

    today = today or date.today()
    latest = months[-1]
    age = (today.year - latest.year) * 12 + (today.month - latest.month)
    if age > recency_months:
        diagnostics.append(f"most recent observation {latest.isoformat()} is {age} months old (> {recency_months})")

    return diagnostics


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def _build_metadata(description: str, key_word: list[str]) -> dict:
    """Echo the request into metadata: title/description from the description,
    keywords from the incoming list enriched with generic demand terms."""
    title = description.strip()
    meta_description = title if title.endswith(".") else f"{title}."

    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in (*key_word, *ENRICHMENT_KEYWORDS):
        cleaned = candidate.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            keywords.append(cleaned)

    return {"title": title, "description": meta_description, "keywords": keywords}


def get_timeseries(description: str, key_word: list[str] | None = None) -> dict:
    """Return the time series + metadata for a description/keywords request.

    This is the importable entry point the orchestrator calls directly; the HTTP
    endpoint is a thin wrapper around it.
    """
    key_word = list(key_word or [])

    source = select_source(description, key_word)
    if source is not None:  # pragma: no cover - live fetching not wired yet
        logger.info("selected source %s for %r", source.name, description)
        # TODO: fetch + normalize from `source`; fall back to mock on failure.

    series = _load_mock_timeseries()

    diagnostics = validate_timeseries(series)
    if diagnostics:
        logger.warning("timeseries diagnostics for %r: %s", description, "; ".join(diagnostics))

    return {
        "timeseries_metadata": _build_metadata(description, key_word),
        "timeseries": series,
    }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
router = APIRouter(tags=["data-engineer"])


@router.post("/data/timeseries", response_model=TimeseriesResponse)
def post_timeseries(request: TimeseriesRequest) -> JSONResponse:
    """POST /data/timeseries — return the historical series for the request.

    Bad input is rejected by FastAPI with a structured 422; unexpected failures
    return a structured error, never a raw 500.
    """
    try:
        result = get_timeseries(request.description, request.key_word)
        return JSONResponse(content=result)
    except Exception as exc:  # defensive: keep the demo alive with a clean error
        logger.exception("get_timeseries failed for %r", request.description)
        return JSONResponse(
            status_code=500,
            content={"error": "data_engineer_failed", "detail": str(exc)},
        )


# Standalone app so Block 2 runs independently: `uvicorn backend.data_engineer:app`.
# The orchestrator (backend/main.py) can instead `app.include_router(router)`.
app = FastAPI(title="MarketPilot — Data-Engineer Agent", version="1.0.0")
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "data-engineer"}


if __name__ == "__main__":  # pragma: no cover - manual run / regenerate mock
    import argparse

    parser = argparse.ArgumentParser(description="Data-Engineer agent")
    parser.add_argument("--regen-mock", action="store_true", help="regenerate mock/timeseries_icecream.json and exit")
    args = parser.parse_args()

    if args.regen_mock:
        MOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timeseries_metadata": {
                "title": "Average Revenue of Icecream Shops in Vienna",
                "description": "Average monthly revenue index of ice cream shops in Vienna over the last 60 months.",
                "keywords": ["icecream", "restaurants", "weather", "seasons"],
            },
            "timeseries": generate_icecream_series(),
        }
        with MOCK_PATH.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        print(f"wrote {MOCK_PATH}")
    else:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8002)
