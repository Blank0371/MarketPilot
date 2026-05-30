"""Data-Engineer agent (Block 2) for MarketPilot.

Given a description + keywords, returns a historical monthly time series with
metadata. An (atomic) description is routed to the closest supported retail
category (rent, staff costs, foot traffic, …) and a deterministic per-category
generator produces the numbers; descriptions that don't map fall back to a
generic seasonal revenue series. The LLM only *classifies and routes* — it never
invents a number or a series (see ``resolve_series``). The source-registry in
``backend/data_sources.py`` lists the connected (mock) sources; the real/proxy
fetch path (``_adapt_query_response_to_monthly_series``) plugs in later.

Contract (canonical — see FLOW_AND_AGENTS.md §4.2):

    POST /data/timeseries
    request : { "description": str, "keyWord": [str, ...] }
    response: { "timeseries_metadata": { "title", "description", "keywords" },
                "timeseries": { "YYYY-MM-DD": float, ... } }

The same logic is exposed as ``get_timeseries(description, key_word)`` so the
orchestrator can import and call it directly without HTTP.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.data_sources import (
    CONNECTED_SOURCES,
    SOURCE_QUALITIES,
    SUPPORTED_CATEGORIES,
    default_source_for_category,
    is_supported_category,
    source_by_id,
)

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
# Atomic data-request routing (v2)
# ---------------------------------------------------------------------------
# The agent can be handed a single *atomic* data description (e.g. "monthly rent
# for a 1,500 sq ft retail space") and must return a monthly series for the
# closest supported category. The LLM only classifies/routes; every number comes
# from the deterministic generators below. When no LLM is configured a keyword
# classifier takes over, so the pipeline works fully offline.
#
# The public contract is UNCHANGED: get_timeseries still returns
#   { "timeseries_metadata": {...}, "timeseries": { "YYYY-MM-DD": float } }.

# Keyword -> category rules for the no-LLM fallback classifier.
KEYWORD_CATEGORY_RULES: dict[str, tuple[str, ...]] = {
    "rent":                  ("rent", "lease", "retail space", "sq ft", "square foot",
                              "square feet", "licensing fee", "license fee"),
    "staff costs":           ("wage", "salary", "staff", "payroll", "benefits",
                              "employee", "labour", "labor"),
    "location foot traffic": ("foot traffic", "footfall", "pedestrian", "passersby",
                              "passer-by", "visitor count", "storefront"),
    "average basket price":  ("transaction value", "basket", "spending per visit",
                              "spend per visit", "average price", "price per bottle",
                              "average spend"),
    "margin":                ("margin", "profit margin", "gross margin", "markup"),
    "seasonality":           ("seasonal", "seasonality", "holiday", "festival",
                              "monthly fluctuation", "fluctuation", "events that impact"),
    "tourism dependency":    ("tourist", "tourism", "visitors from abroad",
                              "foreign visitor"),
}

# Order matters: more specific categories first so e.g. "average price per bottle"
# resolves to basket price, and "average rent" resolves to rent — not seasonality.
_CATEGORY_PRIORITY: tuple[str, ...] = (
    "rent", "staff costs", "location foot traffic", "average basket price",
    "margin", "tourism dependency", "seasonality",
)

# Revenue cues take priority over factor keywords on the wired pipeline path:
# the DE there receives a composite revenue *title* (translation_agent builds
# "Average revenue of {idea} in Vienna"), not an atomic factor. Without this, an
# idea name embedding a factor word ("staffing", "seasonal", "tourist") would be
# routed to that factor's generator and fed to Sybilion as wrong-magnitude
# revenue history. 'sales' is deliberately EXCLUDED — it occurs in legitimate
# atomic factor descriptions ("wine sales", "profit margin on sales") that must
# keep their factor category; every synthesized title contains the word "revenue".
REVENUE_CUES: tuple[str, ...] = ("revenue", "turnover")

# Per-category salts so two categories sharing a description still differ, while
# the same (description, category) pair is fully repeatable.
_CATEGORY_SALT: dict[str, int] = {
    "rent": 11, "staff costs": 22, "location foot traffic": 33,
    "average basket price": 44, "margin": 55, "seasonality": 66,
    "tourism dependency": 77, "generic": 99,
}


@dataclass
class SeriesResolution:
    """Internal trace of how a description was routed. Logged, never returned."""

    category: str
    source_id: str | None
    source_quality: str  # one of SOURCE_QUALITIES: exact | proxy | mock | none
    reason: str
    monthly_series: dict[str, float]


def _stable_seed(text: str) -> int:
    """Deterministic 32-bit seed from text — repeatable across runs/processes."""
    return int(hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:8], 16)


def _is_revenue_title(description: str) -> bool:
    """True for composite revenue titles (e.g. "Average revenue of X in Vienna").

    These arrive from the wired pipeline (``translation_agent._synthesize_title``)
    and must route to the generic revenue generator, never a factor generator.
    """
    text = (description or "").lower()
    return any(cue in text for cue in REVENUE_CUES)


def _keyword_classify_description(description: str) -> str:
    """Map a description to a supported category by keyword, or 'unsupported'.

    Works with no LLM and no network — the resilient default for the pipeline.
    """
    if _is_revenue_title(description):
        return "unsupported"  # revenue title -> generic revenue series, not a factor
    text = (description or "").lower()
    for category in _CATEGORY_PRIORITY:
        if any(keyword in text for keyword in KEYWORD_CATEGORY_RULES[category]):
            return category
    return "unsupported"


# ---------------------------------------------------------------------------
# Deterministic monthly generators (one per category) — the numbers live here.
# ---------------------------------------------------------------------------
def _standard_months() -> list[date]:
    """The fixed 60-month, first-of-month window the agent reports over.

    The current caller does not pass requested dates, so the agent owns its
    window (matches the legacy mock: 60 points ending _SERIES_LAST_MONTH).
    """
    return _first_of_month_back(_SERIES_LAST_MONTH, _SERIES_MONTHS)


def _series_rng(description: str, category: str) -> random.Random:
    return random.Random(_stable_seed(description) ^ _CATEGORY_SALT.get(category, 0))


def _summer_seasonal(month: int, amplitude: float) -> float:
    """Seasonal multiplier peaking in July, troughing in January (warm-weather
    retail like the ice-cream show case)."""
    return 1.0 + amplitude * math.cos(2 * math.pi * (month - 7) / 12)


def _generate_rent_series(months: list[date], description: str) -> dict[str, float]:
    # Monthly rent (EUR) for a small retail unit: flat with mild annual drift.
    rng = _series_rng(description, "rent")
    base = 3200.0 + rng.uniform(-300, 300)
    return {d.isoformat(): round(base * (1 + 0.0022 * i) + rng.uniform(-15, 15), 2)
            for i, d in enumerate(months)}


def _generate_staff_costs_series(months: list[date], description: str) -> dict[str, float]:
    # Monthly payroll (EUR) for a small team: drift up, small summer uptick.
    rng = _series_rng(description, "staff costs")
    base = 7800.0 + rng.uniform(-600, 600)
    out: dict[str, float] = {}
    for i, d in enumerate(months):
        val = base * (1 + 0.0025 * i) * _summer_seasonal(d.month, 0.03) + rng.uniform(-40, 40)
        out[d.isoformat()] = round(val, 2)
    return out


def _generate_foot_traffic_series(months: list[date], description: str) -> dict[str, float]:
    # Monthly visitors past the storefront: strongly seasonal (summer peak).
    rng = _series_rng(description, "location foot traffic")
    base = 11000.0 + rng.uniform(-1500, 1500)
    out: dict[str, float] = {}
    for i, d in enumerate(months):
        val = base * (1 + 0.0015 * i) * _summer_seasonal(d.month, 0.30) + rng.uniform(-250, 250)
        out[d.isoformat()] = round(max(0.0, val), 1)
    return out


def _generate_average_basket_series(months: list[date], description: str) -> dict[str, float]:
    # Average spend per transaction (EUR): stable with mild trend + tiny season.
    rng = _series_rng(description, "average basket price")
    base = 6.40 + rng.uniform(-0.8, 0.8)
    out: dict[str, float] = {}
    for i, d in enumerate(months):
        val = base * (1 + 0.0018 * i) * _summer_seasonal(d.month, 0.05) + rng.uniform(-0.15, 0.15)
        out[d.isoformat()] = round(max(0.0, val), 2)
    return out


def _generate_margin_series(months: list[date], description: str) -> dict[str, float]:
    # Gross margin (%) — stable in a plausible 5–95 band with a tiny seasonal wobble.
    rng = _series_rng(description, "margin")
    base = 62.0 + rng.uniform(-5, 5)
    out: dict[str, float] = {}
    for d in months:
        val = base + 1.5 * math.cos(2 * math.pi * (d.month - 7) / 12) + rng.uniform(-0.6, 0.6)
        out[d.isoformat()] = round(min(95.0, max(5.0, val)), 2)
    return out


def _generate_seasonality_index_series(months: list[date], description: str) -> dict[str, float]:
    # Seasonal demand multiplier centred on ~1.0, summer-peaked.
    rng = _series_rng(description, "seasonality")
    return {d.isoformat(): round(max(0.0, _summer_seasonal(d.month, 0.40) + rng.uniform(-0.03, 0.03)), 3)
            for d in months}


def _generate_tourism_dependency_series(months: list[date], description: str) -> dict[str, float]:
    # Share of demand from tourists (%) — higher in the summer tourist season.
    rng = _series_rng(description, "tourism dependency")
    base = 35.0 + rng.uniform(-5, 5)
    out: dict[str, float] = {}
    for d in months:
        val = base + 18.0 * math.cos(2 * math.pi * (d.month - 7) / 12) + rng.uniform(-1.5, 1.5)
        out[d.isoformat()] = round(min(95.0, max(0.0, val)), 2)
    return out


def _generate_generic_mock_series(months: list[date], description: str) -> dict[str, float]:
    # Fallback for unmapped/revenue-like descriptions: the proven seasonal
    # revenue shape (summer peak, mild uptrend) so the show case stays intact.
    rng = _series_rng(description, "generic")
    out: dict[str, float] = {}
    for i, d in enumerate(months):
        trend = _SERIES_BASE + _SERIES_TREND_PER_MONTH * i
        seasonal = _summer_seasonal(d.month, _SERIES_SEASONAL_AMPLITUDE)
        out[d.isoformat()] = round(trend * seasonal + rng.uniform(-_SERIES_NOISE, _SERIES_NOISE), 1)
    return out


_CATEGORY_GENERATORS = {
    "rent": _generate_rent_series,
    "staff costs": _generate_staff_costs_series,
    "location foot traffic": _generate_foot_traffic_series,
    "average basket price": _generate_average_basket_series,
    "margin": _generate_margin_series,
    "seasonality": _generate_seasonality_index_series,
    "tourism dependency": _generate_tourism_dependency_series,
}


def _generate_monthly_series(
    category: str,
    source_quality: str,  # noqa: ARG001 — reserved for real/proxy weighting later
    months: list[date],
    description: str,
) -> dict[str, float]:
    """Dispatch to the category generator; unknown categories get the generic one."""
    generator = _CATEGORY_GENERATORS.get(category, _generate_generic_mock_series)
    return generator(months, description)


# ---------------------------------------------------------------------------
# Monthly normalisation + big-agent adapter (real/proxy path — written, unwired)
# ---------------------------------------------------------------------------
_QUARTER_MONTHS: dict[str, tuple[int, int, int]] = {
    "Q1": (1, 2, 3), "Q2": (4, 5, 6), "Q3": (7, 8, 9), "Q4": (10, 11, 12),
}


def _to_month_start(date_like: str) -> list[str]:
    """Normalise a date token to one or more first-of-month ISO strings.

    Supports ``YYYY-MM-DD``, ``YYYY-MM``, ``YYYY-Qn`` (→ 3 months) and ``YYYY``
    (→ 12 months) so quarterly/annual sources still land on monthly keys.
    """
    s = str(date_like).strip().upper().replace("/", "-")
    if "Q" in s:
        year, _, quarter = s.partition("-")
        months = _QUARTER_MONTHS.get(quarter.strip())
        if months and year.isdigit():
            return [date(int(year), m, 1).isoformat() for m in months]
        raise ValueError(f"unparseable quarter token {date_like!r}")
    parts = s.split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return [date(int(parts[0]), int(parts[1]), 1).isoformat()]
    if len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 4:
        return [date(int(parts[0]), m, 1).isoformat() for m in range(1, 13)]
    raise ValueError(f"unparseable date token {date_like!r}")


def _adapt_query_response_to_monthly_series(response: dict) -> dict[str, float]:
    """Adapt a big-agent ``QueryResponse``-like dict to the monthly contract.

    Rows live under ``data`` (list of ``{date, value}`` points). Dates may be
    ``YYYY-MM-DD`` / ``YYYY-MM`` / ``YYYY-Qn`` / ``YYYY``; all are normalised to
    month starts and duplicate months are averaged. Written for the future
    real/proxy path — not wired into ``get_timeseries`` yet (mock-only).
    """
    rows = response.get("data") or response.get("rows") or []
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_date = row.get("date") or row.get("period") or row.get("month")
        raw_val = row.get("value", row.get("val"))
        if raw_date is None or raw_val is None:
            continue
        try:
            value = float(raw_val)
        except (TypeError, ValueError):
            continue
        try:
            month_keys = _to_month_start(raw_date)
        except ValueError:
            continue
        for key in month_keys:
            buckets.setdefault(key, []).append(value)
    series = {k: round(sum(v) / len(v), 4) for k, v in buckets.items() if v}
    return dict(sorted(series.items()))


# ---------------------------------------------------------------------------
# LLM routing (Featherless) — classify + select a source. Never numbers.
# ---------------------------------------------------------------------------
_LLM_ROUTING_SYSTEM = (
    "You are a data routing classifier for an offline retail planning agent. "
    "You map one atomic data description to one supported category and select one "
    "source from the provided connected sources. You never invent numbers, never "
    "produce a time series, and never invent source IDs. Return only valid JSON."
)


def _llm_routing_user(description: str, sources: list[dict]) -> str:
    categories = "\n".join(f"- {c}" for c in (*SUPPORTED_CATEGORIES, "unsupported"))
    return (
        "Supported categories:\n" + categories + "\n\n"
        "Rules:\n"
        "- Do not invent numbers or a time series.\n"
        "- Select source_id only from the connected sources below (or null).\n"
        "- If no real/proxy source fits, pick the deterministic mock source for the closest category.\n"
        '- If it cannot map to any supported category, use category "unsupported", '
        'source_quality "none", source_id null.\n'
        '- aggregation must be "monthly".\n\n'
        f"Connected sources:\n{json.dumps(sources, indent=2)}\n\n"
        f"Description:\n{description}\n\n"
        "Return exactly this JSON shape:\n"
        '{"category":"...","source_id":"... or null","source_quality":"exact|proxy|mock|none",'
        '"aggregation":"monthly","unit_hint":"...","confidence":"low|medium|high",'
        '"fallback_required":true,"reason":"short explanation"}'
    )


def _extract_json_object(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(text[start: end + 1])


def _validate_llm_routing(data: dict) -> dict | None:
    """Validate + sanitise an LLM routing dict; return None to reject it.

    Enforces the hard relevance rules: category must be supported (or the
    explicit 'unsupported'); a named source must exist in CONNECTED_SOURCES AND
    cover the category, otherwise it is dropped and the quality downgraded. The
    LLM can therefore never inject an unknown category, source, or any number.
    """
    if not isinstance(data, dict):
        return None
    category = str(data.get("category", "")).strip().lower()
    if category != "unsupported" and not is_supported_category(category):
        return None

    quality = str(data.get("source_quality", "")).strip().lower()
    if quality not in SOURCE_QUALITIES:
        quality = "none" if category == "unsupported" else "mock"

    source_id = data.get("source_id")
    source_id = source_id.strip() or None if isinstance(source_id, str) else None
    if source_id is not None:
        src = source_by_id(source_id)
        if src is None or (category != "unsupported" and category not in src.get("categories", [])):
            source_id = None
            quality = "none" if category == "unsupported" else "mock"

    reason = str(data.get("reason", "")).strip() or "LLM routing"
    return {"category": category, "source_id": source_id, "source_quality": quality, "reason": reason}


def _llm_resolve_data_request(description: str, sources: list[dict]) -> dict | None:
    """Classify + route one description with the Featherless LLM.

    Returns a validated routing dict, or None on any failure (no key, network
    error, bad JSON, invalid selection) so the caller can fall back to keywords.
    Reuses the same FeatherlessClient pattern as the translation agent. Never
    returns numeric series values.
    """
    if not os.getenv("FEATHERLESS_API_KEY"):
        return None
    try:
        from backend.translation_agent import FeatherlessClient  # reuse Block 3 client
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("FeatherlessClient unavailable (%s); skipping LLM routing", exc)
        return None

    client = FeatherlessClient()
    if not client.available:
        return None
    try:
        raw = client.chat(
            _LLM_ROUTING_SYSTEM,
            _llm_routing_user(description, sources),
            temperature=0.0,
            max_tokens=200,
        )
        data = _extract_json_object(raw)
    except Exception as exc:
        logger.warning("LLM routing failed for %r (%s); using keyword fallback", description, exc)
        return None
    routing = _validate_llm_routing(data)
    if routing is None:
        logger.warning("LLM routing for %r rejected by validation; using keyword fallback", description)
    return routing


def resolve_series(description: str, key_word: list[str] | None = None) -> SeriesResolution:
    """Classify a description, pick a source, and generate its monthly series.

    Flow: LLM routing (if configured) -> validation -> keyword fallback. The LLM
    classifies/routes only; the deterministic generators produce every number.
    Always succeeds — unmapped descriptions get a generic seasonal series.
    """
    months = _standard_months()

    # Composite revenue titles are NOT atomic factor requests: route straight to
    # the generic revenue generator (skipping the LLM) so a business name that
    # embeds a factor word cannot hijack the revenue series. See REVENUE_CUES.
    if _is_revenue_title(description):
        return SeriesResolution(
            category="revenue",
            source_id=None,
            source_quality="mock",
            reason="Composite revenue title — generic deterministic revenue series.",
            monthly_series=_generate_generic_mock_series(months, description),
        )

    routing = _llm_resolve_data_request(description, CONNECTED_SOURCES)
    if routing is None:
        category = _keyword_classify_description(description)
        if category == "unsupported":
            reason = "No LLM routing; keyword classifier found no supported category — generic mock."
            source = None
        else:
            reason = f"No LLM routing; keyword classifier matched {category!r} — deterministic mock."
            source = default_source_for_category(category)
        routing = {
            "category": category,
            "source_id": source["id"] if source else None,
            "source_quality": "mock" if source else "none",
            "reason": reason,
        }

    category = routing["category"]
    # Mock-only iteration: every selected source is a deterministic mock. The
    # real/proxy fetch path (with timeout + _adapt_query_response_to_monthly_series)
    # plugs in right here later.
    gen_category = category if category != "unsupported" else "generic"
    series = _generate_monthly_series(gen_category, routing["source_quality"], months, description)

    return SeriesResolution(
        category=category,
        source_id=routing["source_id"],
        source_quality=routing["source_quality"],
        reason=routing["reason"],
        monthly_series=series,
    )


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

    Routes the description to the closest supported category and generates a
    deterministic monthly series for it (``resolve_series``). This is the
    importable entry point the orchestrator calls directly; the HTTP endpoint is
    a thin wrapper around it. The public shape is unchanged.
    """
    key_word = list(key_word or [])

    resolution = resolve_series(description, key_word)
    logger.info(
        "data-request %r -> category=%s source=%s quality=%s (%s)",
        description, resolution.category, resolution.source_id,
        resolution.source_quality, resolution.reason,
    )
    series = resolution.monthly_series

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
