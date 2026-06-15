from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
import requests

from data_engineer_core.schemas.result_schema import TimeSeriesPoint


@dataclass(frozen=True)
class EurostatDatasetConfig:
    dataset_code: str
    params: dict[str, str]
    metric: str
    unit: str
    source_label: str


class EurostatAdapter:
    BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

    def fetch_timeseries(
        self,
        dataset_id: str,
        metric: str,
        last_years: int | None,
        geo_code: str | None,
    ) -> list[TimeSeriesPoint]:
        config = self._config_for_dataset(dataset_id, geo_code or "AT")
        payload = self._fetch_json(config)

        value_map: dict[str, float] = payload.get("value", {})
        time_labels = self._extract_time_labels(payload)
        if not value_map or not time_labels:
            return []

        points: list[TimeSeriesPoint] = []
        # For filtered requests we expect one non-time series, so index maps directly to time positions.
        for i, time_key in enumerate(time_labels):
            raw = value_map.get(str(i))
            if raw is None:
                continue
            points.append(
                TimeSeriesPoint(
                    date=self._normalize_time_label(time_key),
                    region=geo_code or "AT",
                    metric=metric,
                    value=float(raw),
                    unit=config.unit,
                    source=config.source_label,
                    dataset_id=dataset_id,
                )
            )

        points.sort(key=lambda x: x.date)
        if last_years and last_years > 0:
            cutoff = date.today().year - last_years
            points = [p for p in points if self._year_from_label(p.date) >= cutoff]
        return points

    def _fetch_json(self, config: EurostatDatasetConfig) -> dict:
        url = f"{self.BASE_URL}/{config.dataset_code}"
        response = requests.get(url, params=config.params, timeout=30)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_time_labels(payload: dict) -> list[str]:
        time_dim = payload.get("dimension", {}).get("time")
        if not time_dim:
            return []
        category = time_dim.get("category", {})
        index = category.get("index", {})
        if isinstance(index, list):
            return index
        if isinstance(index, dict):
            ordered = sorted(index.items(), key=lambda x: x[1])
            return [item[0] for item in ordered]
        return []

    @staticmethod
    def _year_from_label(label: str) -> int:
        # Supports formats like 2024-01, 2024M01, 2024-Q1, 2024.
        for token in [label[:4], label.split("-")[0]]:
            if token.isdigit() and len(token) == 4:
                return int(token)
        digits = "".join(ch for ch in label if ch.isdigit())
        if len(digits) >= 4:
            return int(digits[:4])
        return 0

    @staticmethod
    def _normalize_time_label(label: str) -> str:
        if re_match := re.match(r"^(\d{4})M(\d{2})$", label):
            return f"{re_match.group(1)}-{re_match.group(2)}"
        if re_match := re.match(r"^(\d{4})Q([1-4])$", label):
            return f"{re_match.group(1)}-Q{re_match.group(2)}"
        return label

    @staticmethod
    def _config_for_dataset(dataset_id: str, geo_code: str) -> EurostatDatasetConfig:
        common = {"lang": "en", "format": "JSON", "geo": geo_code}
        if dataset_id == "eurostat_hicp_rent_index_austria":
            return EurostatDatasetConfig(
                dataset_code="prc_hicp_midx",
                params={**common, "coicop": "CP041", "freq": "M", "unit": "I15"},
                metric="average_rent",
                unit="index_2015_100",
                source_label="Eurostat",
            )
        if dataset_id == "eurostat_hicp_all_items":
            return EurostatDatasetConfig(
                dataset_code="prc_hicp_midx",
                params={**common, "coicop": "CP00", "freq": "M", "unit": "I15"},
                metric="inflation_index",
                unit="index_2015_100",
                source_label="Eurostat",
            )
        if dataset_id == "eurostat_unemployment_rate":
            return EurostatDatasetConfig(
                dataset_code="une_rt_m",
                params={
                    **common,
                    "freq": "M",
                    "s_adj": "SA",
                    "sex": "T",
                    "age": "TOTAL",
                    "unit": "PC_ACT",
                },
                metric="unemployment_rate",
                unit="percent_of_active_population",
                source_label="Eurostat",
            )
        if dataset_id == "eurostat_gdp_nominal_quarterly":
            return EurostatDatasetConfig(
                dataset_code="namq_10_gdp",
                params={
                    **common,
                    "freq": "Q",
                    "na_item": "B1GQ",
                    "unit": "CP_MEUR",
                    "s_adj": "SCA",
                },
                metric="gdp_nominal",
                unit="million_eur",
                source_label="Eurostat",
            )
        raise ValueError(f"Unsupported Eurostat dataset: {dataset_id}")
