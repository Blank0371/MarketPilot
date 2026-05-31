from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.data_engineer_core.adapters.commodities import CommodityConnector
from backend.data_engineer_core.adapters.eurostat import EurostatAdapter
from backend.data_engineer_core.adapters.statistik_austria import StatistikAustriaAdapter
from backend.data_engineer_core.agents.intent_extractor import IntentExtractor
from backend.data_engineer_core.agents.source_planner import SourcePlanner
from backend.data_engineer_core.config import settings
from backend.data_engineer_core.registry.loader import RegistryLoader
from backend.data_engineer_core.schemas.result_schema import TimeSeriesPoint


@dataclass
class RealDataResult:
    series: dict[str, float]
    status: str
    source_ref: str
    limitations: list[str]


def _to_month_start(label: str) -> list[str]:
    s = str(label).strip().upper().replace("/", "-")
    if "Q" in s:
        year, _, quarter = s.partition("-")
        if year.isdigit() and quarter in {"Q1", "Q2", "Q3", "Q4"}:
            start = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}[quarter]
            return [date(int(year), start + offset, 1).isoformat() for offset in range(3)]
        return []

    parts = s.split("-")
    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
        return [date(int(parts[0]), int(parts[1]), 1).isoformat()]
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return [date(int(parts[0]), int(parts[1]), 1).isoformat()]
    if len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 4:
        return [date(int(parts[0]), m, 1).isoformat() for m in range(1, 13)]
    return []


def _adapt_points(points: list[TimeSeriesPoint]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for point in points:
        for month_key in _to_month_start(point.date):
            buckets.setdefault(month_key, []).append(float(point.value))
    return {
        key: round(sum(values) / len(values), 4)
        for key, values in sorted(buckets.items())
        if values
    }


class CoreRealDataProvider:
    def __init__(self) -> None:
        loader = RegistryLoader(settings.sources_path, settings.datasets_path)
        self.intent_extractor = IntentExtractor()
        self.source_planner = SourcePlanner(loader)
        self.eurostat = EurostatAdapter()
        self.commodities = CommodityConnector()
        self.statistik_austria = StatistikAustriaAdapter()

    def fetch(self, query: str) -> RealDataResult | None:
        interpreted = self.intent_extractor.extract(query)
        plan = self.source_planner.plan(interpreted)

        if plan.status in {"no_data", "auth_required"} or not plan.selected_candidates:
            return None

        candidate = plan.selected_candidates[0]
        points: list[TimeSeriesPoint]
        limitations = list(plan.limitations)

        try:
            if candidate.source_id == "eurostat":
                points = self.eurostat.fetch_timeseries(
                    dataset_id=candidate.dataset_id,
                    metric=interpreted.metric,
                    last_years=interpreted.time_range.last_years,
                    geo_code=interpreted.geo.country,
                )
            elif candidate.source_id == "statistik_austria_open_data":
                points = self.statistik_austria.fetch_timeseries(
                    dataset_id=candidate.dataset_id,
                    metric=interpreted.metric,
                    last_years=interpreted.time_range.last_years,
                )
            elif candidate.source_id == "yahoo_finance_commodities":
                points = self.commodities.fetch_timeseries(
                    raw_query=interpreted.raw_text,
                    last_years=interpreted.time_range.last_years,
                )
            else:
                return None
        except Exception:
            return None

        if not points:
            return None

        series = _adapt_points(points)
        if not series:
            return None

        return RealDataResult(
            series=series,
            status="partial" if plan.status == "partial" else "success",
            source_ref=f"{candidate.source_id}:{candidate.dataset_id}",
            limitations=limitations,
        )

    def fetch_by_selection(
        self,
        *,
        dataset_id: str,
        metric: str,
        raw_query: str,
        last_years: int = 10,
    ) -> RealDataResult | None:
        points: list[TimeSeriesPoint]
        source_ref = ""
        try:
            if dataset_id.startswith("eurostat_"):
                points = self.eurostat.fetch_timeseries(
                    dataset_id=dataset_id,
                    metric=metric,
                    last_years=last_years,
                    geo_code="AT",
                )
                source_ref = f"eurostat:{dataset_id}"
            elif dataset_id.startswith("statistik_austria_"):
                points = self.statistik_austria.fetch_timeseries(
                    dataset_id=dataset_id,
                    metric=metric,
                    last_years=last_years,
                )
                source_ref = f"statistik_austria_open_data:{dataset_id}"
            elif dataset_id == "yahoo_finance_commodities_monthly":
                points = self.commodities.fetch_timeseries(
                    raw_query=raw_query,
                    last_years=last_years,
                )
                source_ref = "yahoo_finance_commodities:yahoo_finance_commodities_monthly"
            else:
                return None
        except Exception:
            return None

        if not points:
            return None
        series = _adapt_points(points)
        if not series:
            return None
        return RealDataResult(series=series, status="success", source_ref=source_ref, limitations=[])
