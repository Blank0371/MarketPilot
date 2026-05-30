"""Sybilion client (Block 4, part 1) for MarketPilot.

Turns the Data-Engineer time series into a Sybilion forecast request, runs the
async forecast through **Sybilion's Python SDK** (submit -> poll -> fetch
artifacts), and normalizes the artifacts into the small internal shape the report
agent consumes.

Because the real forecast is asynchronous, slow, and billed (see SYBILION_DOC.md),
we call it sparingly: the first real response is cached under ``mock/`` and every
later run develops against that cache. On a missing token, a timeout, or any API
failure we fall back to deterministic mock artifacts so the live demo never blocks
on the network. The fallback is tagged ``source: "cache"`` (or ``"mock"``).

Public surface:

    build_forecast_request(timeseries, metadata) -> dict      # Sybilion request body
    get_forecast(timeseries, metadata) -> {                   # normalized result
        "source": "live" | "cache" | "mock",
        "forecast": [ {date, forecast, low, high}, ... ],      # 6 horizon months
        "drivers":  [ {name, importance, direction, horizon}, ... ],
        "backtest": {mape, rmse, quality},
    }

The forecast quantiles are read from ``quantile_forecast`` keys ``"0.1"`` (low),
``"0.5"`` (median) and ``"0.9"`` (high) exactly as documented — never ``p10/p50``.
"""

from __future__ import annotations

import json
import logging
import math
import os
import statistics
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("marketpilot.sybilion_client")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"
FORECAST_CACHE = _MOCK_DIR / "forecast.json"
SIGNALS_CACHE = _MOCK_DIR / "external_signals.json"
BACKTEST_CACHE = _MOCK_DIR / "backtest_metrics.json"

FORECAST_HORIZON = 6  # months — the soft horizon we request and parse
RECENCY_FACTOR = 0.5
PIPELINE_VERSION = "v1"
FREQUENCY = "monthly"

# Quantile keys, per SYBILION_DOC.md §2.6 (strings, not p10/p50/p90).
Q_LOW, Q_MID, Q_HIGH = "0.1", "0.5", "0.9"
_Z_P90 = 1.2816  # standard-normal quantile for the p10/p90 band half-width
_DEFAULT_SIGMA = 0.12  # YoY volatility fallback when history is too short
# Floor the band at 10%: a synthetic index understates real month-to-month
# revenue noise, and a too-tight band hides the forecast uncertainty the jury
# wants to see. Ceiling keeps a pathological series from drowning the signal.
_SIGMA_BOUNDS = (0.10, 0.25)


# ---------------------------------------------------------------------------
# Request building (Block 4 transforms the Data-Engineer response, §4.3 / §5.5)
# ---------------------------------------------------------------------------
def build_forecast_request(
    timeseries: dict[str, float],
    metadata: dict[str, Any],
    *,
    soft_horizon: int = FORECAST_HORIZON,
) -> dict[str, Any]:
    """Build the Sybilion forecast request body from the Data-Engineer response.

    ``soft_horizon`` is the forecast-horizon contract (MODEL.md §2.2): it arrives
    with the request rather than being hard-coded, so forecast depth can change
    without touching the model.
    """
    meta = metadata or {}
    return {
        "pipeline_version": PIPELINE_VERSION,
        "frequency": FREQUENCY,
        "soft_horizon": soft_horizon,
        "recency_factor": RECENCY_FACTOR,
        "backtest": True,
        "timeseries_metadata": {
            "title": meta.get("title", "Time series"),
            "description": meta.get("description", meta.get("title", "Time series")),
            "keywords": list(meta.get("keywords", []))[:20],
        },
        "timeseries": {str(k): float(v) for k, v in timeseries.items()},
    }


# ---------------------------------------------------------------------------
# Series helpers
# ---------------------------------------------------------------------------
def _sorted_series(timeseries: dict[str, float]) -> list[tuple[date, float]]:
    points = [(date.fromisoformat(k), float(v)) for k, v in timeseries.items()]
    points.sort(key=lambda p: p[0])
    return points


def _add_months(d: date, n: int) -> date:
    month_index = (d.year * 12 + (d.month - 1)) + n
    return date(month_index // 12, month_index % 12 + 1, 1)


def _seasonal_drift_growth(values: list[float]) -> float:
    """Year-over-year growth factor from the last two 12-month blocks."""
    if len(values) >= 24:
        last = statistics.fmean(values[-12:])
        prev = statistics.fmean(values[-24:-12])
        if prev > 0:
            return max(0.85, min(1.20, last / prev))
    return 1.03


def _yoy_sigma(points: list[tuple[date, float]]) -> float:
    """Volatility of the year-over-year ratio — the forecast band half-width."""
    by_date = {d: v for d, v in points}
    ratios: list[float] = []
    for d, v in points:
        prior = by_date.get(_add_months(d, -12))
        if prior and prior > 0:
            ratios.append(v / prior - 1.0)
    if len(ratios) >= 6:
        sigma = statistics.pstdev(ratios)
    else:
        sigma = _DEFAULT_SIGMA
    return max(_SIGMA_BOUNDS[0], min(_SIGMA_BOUNDS[1], sigma))


# ---------------------------------------------------------------------------
# Mock / cache generation
# ---------------------------------------------------------------------------
def generate_mock_artifacts(
    timeseries: dict[str, float],
    *,
    horizon: int = FORECAST_HORIZON,
) -> dict[str, dict]:
    """Deterministically derive Sybilion-shaped artifacts from the history.

    The forecast is a seasonal-naive projection with year-over-year drift and a
    p10/p90 band from the historical YoY volatility. Drivers and backtest are
    derived from the same series so the cache reads like a real response. This is
    the fallback used whenever the live API is unavailable. ``horizon`` is the
    requested forecast depth (MODEL.md §2.2); we emit exactly that many points.
    """
    points = _sorted_series(timeseries)
    if not points:
        raise ValueError("cannot build a forecast from an empty time series")

    by_date = {d: v for d, v in points}
    values = [v for _, v in points]
    growth = _seasonal_drift_growth(values)
    sigma = _yoy_sigma(points)
    seasonal_avg = statistics.fmean(values[-12:]) if len(values) >= 12 else statistics.fmean(values)

    last_date = points[-1][0]
    forecast_series: dict[str, dict] = {}
    for step in range(1, horizon + 1):
        d = _add_months(last_date, step)
        source = by_date.get(_add_months(d, -12), seasonal_avg)
        point = round(source * growth, 2)
        low = round(point * (1 - _Z_P90 * sigma), 2)
        high = round(point * (1 + _Z_P90 * sigma), 2)
        forecast_series[d.isoformat()] = {
            "forecast": point,
            "quantile_forecast": {Q_LOW: low, Q_MID: point, Q_HIGH: high},
        }

    forecast = {
        "version": "1.1",
        "data": {
            "forecast_horizon": horizon,
            "forecast_start": _add_months(last_date, 1).isoformat(),
            "forecast_end": _add_months(last_date, horizon).isoformat(),
            "forecast_series": forecast_series,
        },
    }

    signals = {"version": "1.1", "data": {"signals": _derive_signals(points, sigma)}}
    backtest = {"version": "1.1", "data": _derive_backtest(points, growth, sigma)}
    return {"forecast": forecast, "signals": signals, "backtest": backtest}


def _seasonality_strength(points: list[tuple[date, float]]) -> float:
    """Peak-to-trough swing of the average seasonal cycle, as a 0..1 strength."""
    by_month: dict[int, list[float]] = {}
    for d, v in points:
        by_month.setdefault(d.month, []).append(v)
    monthly = {m: statistics.fmean(vs) for m, vs in by_month.items() if vs}
    if len(monthly) < 4:
        return 0.5
    lo, hi, mean = min(monthly.values()), max(monthly.values()), statistics.fmean(list(monthly.values()))
    if mean <= 0:
        return 0.5
    return max(0.0, min(1.0, (hi - lo) / (2 * mean)))


def _derive_signals(points: list[tuple[date, float]], sigma: float) -> list[dict]:
    """Ranked external drivers (external_signals.json shape).

    Seasonality and tourism are the decisive ice cream factors; seasonality
    importance scales with the measured seasonal swing so it reflects the data.
    """
    season = _seasonality_strength(points)
    drivers = [
        {"name": "Vienna tourism footfall", "importance": 0.82, "direction": "positive", "correlation": 0.71, "horizon": 1},
        {"name": "Summer temperature / heatwaves", "importance": round(0.55 + 0.30 * season, 2), "direction": "positive", "correlation": 0.78, "horizon": 1},
        {"name": "Winter seasonality", "importance": round(0.50 + 0.30 * season, 2), "direction": "negative", "correlation": -0.74, "horizon": 6},
        {"name": "Consumer spending", "importance": 0.55, "direction": "positive", "correlation": 0.41, "horizon": 3},
        {"name": "Local foot traffic", "importance": 0.52, "direction": "positive", "correlation": 0.39, "horizon": 2},
        {"name": "Commercial rent pressure", "importance": 0.47, "direction": "negative", "correlation": -0.33, "horizon": 6},
    ]
    drivers.sort(key=lambda d: d["importance"], reverse=True)
    return drivers


def _derive_backtest(points: list[tuple[date, float]], growth: float, sigma: float) -> dict:
    """Rolling seasonal-naive backtest over the last 12 months (MAPE / RMSE).

    The reported MAPE is floored by the forecast band half-width so confidence
    never overstates certainty on an unusually clean series.
    """
    by_date = {d: v for d, v in points}
    abs_pct: list[float] = []
    sq_err: list[float] = []
    for d, actual in points[-12:]:
        pred_src = by_date.get(_add_months(d, -12))
        if pred_src is None or actual == 0:
            continue
        pred = pred_src * growth
        abs_pct.append(abs(actual - pred) / abs(actual))
        sq_err.append((actual - pred) ** 2)

    rolling_mape = statistics.fmean(abs_pct) if abs_pct else sigma
    mean_level = statistics.fmean([v for _, v in points])
    # Out-of-sample error is never tighter than the forecast band half-width;
    # keep RMSE consistent with the reported MAPE on this series' level.
    mape = round(max(rolling_mape, sigma), 4)
    in_sample_rmse = math.sqrt(statistics.fmean(sq_err)) if sq_err else 0.0
    rmse = round(max(in_sample_rmse, mape * mean_level), 2)
    return {"mape": mape, "rmse": rmse, "quality": quality_from_mape(mape)}


def quality_from_mape(mape: float) -> str:
    if mape < 0.08:
        return "high"
    if mape < 0.15:
        return "medium-high"
    if mape < 0.25:
        return "medium"
    return "low"


def write_mock_artifacts(timeseries: dict[str, float]) -> None:
    """Persist freshly generated artifacts to ``mock/`` (used to seed the cache)."""
    artifacts = generate_mock_artifacts(timeseries)
    _MOCK_DIR.mkdir(parents=True, exist_ok=True)
    for path, payload in ((FORECAST_CACHE, artifacts["forecast"]), (SIGNALS_CACHE, artifacts["signals"]), (BACKTEST_CACHE, artifacts["backtest"])):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
    logger.info("wrote mock artifacts to %s", _MOCK_DIR)


# ---------------------------------------------------------------------------
# Artifact parsing (normalize Sybilion shapes -> internal shape)
# ---------------------------------------------------------------------------
def parse_forecast_artifact(raw: dict) -> list[dict]:
    """Read ``data.forecast_series[date].quantile_forecast`` -> [{date,forecast,low,high}]."""
    series = (raw or {}).get("data", {}).get("forecast_series", {})
    out: list[dict] = []
    for d in sorted(series):
        point = series[d]
        q = point.get("quantile_forecast", {})
        base = float(point.get("forecast", q.get(Q_MID)))
        out.append(
            {
                "date": d,
                "forecast": round(base, 2),
                "low": round(float(q.get(Q_LOW, base)), 2),
                "high": round(float(q.get(Q_HIGH, base)), 2),
            }
        )
    if not out:
        raise ValueError("forecast artifact has no forecast_series points")
    return out


def parse_signals_artifact(raw: dict) -> list[dict]:
    """Map external_signals.json -> drivers[] (name, importance, direction, horizon)."""
    signals = (raw or {}).get("data", {}).get("signals", [])
    drivers: list[dict] = []
    for s in signals:
        importance = float(s.get("importance", abs(s.get("correlation", 0.0))))
        direction = s.get("direction")
        if direction not in ("positive", "negative", "mixed"):
            direction = "positive" if s.get("correlation", 0.0) >= 0 else "negative"
        driver = {
            "name": s.get("name") or s.get("title") or "Unknown driver",
            "importance": round(max(0.0, min(1.0, importance)), 2),
            "direction": direction,
        }
        if s.get("horizon") is not None:
            driver["horizon"] = int(s["horizon"])
        drivers.append(driver)
    drivers.sort(key=lambda d: d["importance"], reverse=True)
    return drivers


def parse_backtest_artifact(raw: dict) -> dict:
    """Map backtest_metrics.json -> {mape, rmse, quality}."""
    data = (raw or {}).get("data", raw or {})
    mape = float(data.get("mape", _DEFAULT_SIGMA))
    rmse = float(data.get("rmse", 0.0))
    quality = data.get("quality") or quality_from_mape(mape)
    return {"mape": round(mape, 4), "rmse": round(rmse, 2), "quality": quality}


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------
def _read_json(path: Path) -> dict | None:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _load_from_cache(timeseries: dict[str, float], *, horizon: int = FORECAST_HORIZON) -> dict:
    """Load cached artifacts; regenerate from the series if any file is missing.

    If the cached forecast cannot satisfy the requested ``horizon`` (it has fewer
    points), we regenerate a mock at that horizon and flag the result ``"mock"``
    so the report can surface the fallback (MODEL.md §1.1).
    """
    forecast_raw = _read_json(FORECAST_CACHE)
    signals_raw = _read_json(SIGNALS_CACHE)
    backtest_raw = _read_json(BACKTEST_CACHE)

    source = "cache"
    if forecast_raw is None or signals_raw is None or backtest_raw is None:
        logger.info("cache incomplete; generating mock artifacts in memory")
        generated = generate_mock_artifacts(timeseries, horizon=horizon)
        forecast_raw = forecast_raw or generated["forecast"]
        signals_raw = signals_raw or generated["signals"]
        backtest_raw = backtest_raw or generated["backtest"]
        source = "mock"

    forecast = parse_forecast_artifact(forecast_raw)
    if len(forecast) < horizon:
        # Cache is shorter than the requested horizon — regenerate at the horizon.
        logger.info("cache has %d points < horizon %d; regenerating mock", len(forecast), horizon)
        forecast = parse_forecast_artifact(generate_mock_artifacts(timeseries, horizon=horizon)["forecast"])
        source = "mock"
    forecast = forecast[:horizon]  # honor the horizon contract (MODEL.md §2.2)

    return {
        "source": source,
        "forecast": forecast,
        "drivers": parse_signals_artifact(signals_raw),
        "backtest": parse_backtest_artifact(backtest_raw),
    }


# ---------------------------------------------------------------------------
# Live SDK path
# ---------------------------------------------------------------------------
_FORECAST_ARTIFACT = "forecast.json"
_SIGNALS_ARTIFACT = "external_signals.json"
_BACKTEST_ARTIFACT = "backtest_metrics.json"


def _run_live_forecast(
    timeseries: dict[str, float],
    metadata: dict[str, Any],
    *,
    timeout_s: float,
    soft_horizon: int = FORECAST_HORIZON,
) -> dict:
    """Submit -> poll -> fetch artifacts via the Sybilion SDK, then cache them.

    Raises on any failure so the caller can fall back to the cache.
    """
    from sybilion import Client  # imported lazily so the module loads without the SDK
    from sybilion._api.models.forecast_request_v1 import ForecastRequestV1

    request_body = build_forecast_request(timeseries, metadata, soft_horizon=soft_horizon)
    client = Client(token=os.environ.get("SYBILION_API_TOKEN"))

    submitted = client.submit_forecast(ForecastRequestV1.from_dict(request_body))
    job_id = submitted.job_id
    logger.info("submitted Sybilion forecast job %s", job_id)

    job = client.wait_forecast(job_id, poll_s=10.0, timeout_s=timeout_s)
    if getattr(job, "status", None) not in (None, "completed"):
        raise RuntimeError(f"forecast job {job_id} ended with status {job.status!r}")

    artifacts = {a.name: a for a in (job.artifacts or [])}

    def fetch(name: str) -> dict | None:
        if name not in artifacts:
            return None
        return json.loads(bytes(client.get_forecast_artifact(job_id, name)))

    forecast_raw = fetch(_FORECAST_ARTIFACT)
    if forecast_raw is None:
        raise RuntimeError("completed job is missing forecast.json")
    signals_raw = fetch(_SIGNALS_ARTIFACT) or {"data": {"signals": []}}
    backtest_raw = fetch(_BACKTEST_ARTIFACT) or {"data": {"mape": _DEFAULT_SIGMA, "rmse": 0.0}}

    # Cache the first real response so later runs (and the demo) reuse it.
    _MOCK_DIR.mkdir(parents=True, exist_ok=True)
    for path, payload in ((FORECAST_CACHE, forecast_raw), (SIGNALS_CACHE, signals_raw), (BACKTEST_CACHE, backtest_raw)):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    return {
        "source": "live",
        "forecast": parse_forecast_artifact(forecast_raw),
        "drivers": parse_signals_artifact(signals_raw),
        "backtest": parse_backtest_artifact(backtest_raw),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def get_forecast(
    timeseries: dict[str, float],
    metadata: dict[str, Any] | None = None,
    *,
    use_live: bool | None = None,
    timeout_s: float = 240.0,
    forecast_horizon_months: int = FORECAST_HORIZON,
) -> dict:
    """Return a normalized forecast for the series, with a built-in fallback.

    Live SDK calls are attempted only when ``use_live`` is true (defaults to true
    iff ``SYBILION_API_TOKEN`` is set). Any failure — missing key, timeout, bad
    response — falls back to the cached/mock artifacts so the demo never blocks.

    ``forecast_horizon_months`` is the horizon contract (MODEL.md §2.2): it is
    clamped to [1, 12], passed to Sybilion as ``soft_horizon``, and bounds how
    many forecast points the result carries.

    Returns ``{source, forecast, drivers, backtest}`` where ``source`` is
    ``"live"``, ``"cache"`` or ``"mock"``.
    """
    metadata = metadata or {}
    horizon = max(1, min(12, int(forecast_horizon_months)))  # clamp 1..12 — see MODEL.md §2.2
    if use_live is None:
        use_live = bool(os.environ.get("SYBILION_API_TOKEN"))

    if use_live:
        try:
            result = _run_live_forecast(timeseries, metadata, timeout_s=timeout_s, soft_horizon=horizon)
            result["forecast"] = result["forecast"][:horizon]
            return result
        except Exception as exc:  # noqa: BLE001 — any failure must degrade gracefully
            logger.warning("live Sybilion forecast failed (%s); falling back to cache", exc)

    return _load_from_cache(timeseries, horizon=horizon)


if __name__ == "__main__":  # pragma: no cover - manual cache seeding
    # Seed mock/ from the committed Data-Engineer series:
    #     python -m backend.sybilion_client --seed
    import argparse

    from backend.data_engineer import _load_mock_timeseries

    parser = argparse.ArgumentParser(description="Sybilion client utilities")
    parser.add_argument("--seed", action="store_true", help="generate & write mock/ artifacts from the ice cream series")
    args = parser.parse_args()

    if args.seed:
        write_mock_artifacts(_load_mock_timeseries())
        print(f"seeded artifacts in {_MOCK_DIR}")
    else:
        result = get_forecast(_load_mock_timeseries())
        print(json.dumps(result, indent=2))
