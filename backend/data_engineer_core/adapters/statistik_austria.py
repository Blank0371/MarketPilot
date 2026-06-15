from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

import requests

from data_engineer_core.schemas.result_schema import TimeSeriesPoint


@dataclass(frozen=True)
class StatistikAustriaDatasetConfig:
    csv_file: str
    date_candidates: tuple[str, ...]
    value_candidates: tuple[str, ...]
    source_label: str = "StatistikAustria"


class StatistikAustriaAdapter:
    BASE_URL = "https://data.statistik.gv.at/data"

    def fetch_timeseries(
        self,
        dataset_id: str,
        metric: str,
        last_years: int | None,
    ) -> list[TimeSeriesPoint]:
        cfg = self._config_for_dataset(dataset_id)
        text = self._fetch_csv_text(cfg.csv_file)
        rows = self._parse_csv_rows(text)
        if not rows:
            return []

        points: list[TimeSeriesPoint] = []
        date_key = self._first_present_key(rows[0], cfg.date_candidates)
        value_key = self._first_present_key(rows[0], cfg.value_candidates)
        if not date_key or not value_key:
            return []

        for row in rows:
            raw_date = str(row.get(date_key, "")).strip()
            raw_val = str(row.get(value_key, "")).strip()
            if not raw_date or raw_val in {"", ":", "NA", "nan"}:
                continue
            try:
                value = float(raw_val.replace(",", "."))
            except ValueError:
                continue
            normalized = self._normalize_period(raw_date)
            if normalized is None:
                continue
            points.append(
                TimeSeriesPoint(
                    date=normalized,
                    region="AT",
                    metric=metric,
                    value=value,
                    unit=None,
                    source=cfg.source_label,
                    dataset_id=dataset_id,
                )
            )

        points.sort(key=lambda x: x.date)
        if last_years and last_years > 0:
            cutoff = date.today().year - last_years
            points = [p for p in points if self._year_from_label(p.date) >= cutoff]
        return points

    def _fetch_csv_text(self, csv_file: str) -> str:
        url = f"{self.BASE_URL}/{csv_file}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_csv_rows(text: str) -> list[dict[str, str]]:
        if not text.strip():
            return []
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";"
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        return [dict(row) for row in reader if row]

    @staticmethod
    def _first_present_key(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
        keys = {k.strip().lower(): k for k in row.keys()}
        for candidate in candidates:
            match = keys.get(candidate.lower())
            if match:
                return match
        return None

    @staticmethod
    def _normalize_period(token: str) -> str | None:
        s = token.strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        if len(s) >= 7 and s[4] == "-":
            return f"{s[:7]}-01"
        if len(s) == 4 and s.isdigit():
            return f"{s}-01-01"
        if len(s) == 6 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-01"
        return None

    @staticmethod
    def _year_from_label(label: str) -> int:
        digits = "".join(ch for ch in label if ch.isdigit())
        if len(digits) >= 4:
            return int(digits[:4])
        return 0

    @staticmethod
    def _config_for_dataset(dataset_id: str) -> StatistikAustriaDatasetConfig:
        if dataset_id == "statistik_austria_tourism_nights":
            return StatistikAustriaDatasetConfig(
                csv_file="OGD_touextsai_Tour_HKL_1.csv",
                date_candidates=("C-SDB_TIT-0", "ZEIT", "TIME", "TIME_PERIOD"),
                value_candidates=("F-UEB", "UEB", "VALUE"),
            )
        if dataset_id == "statistik_austria_gross_wages_index":
            return StatistikAustriaDatasetConfig(
                csv_file="OGD_bruttoverdiensteindex2021a_KJID2021_BVIa_1.csv",
                date_candidates=("C-A10-0", "ZEIT", "TIME", "TIME_PERIOD"),
                value_candidates=("F-KJIP_BLG_INSG", "VALUE"),
            )
        if dataset_id == "statistik_austria_hvpi_2025":
            return StatistikAustriaDatasetConfig(
                csv_file="OGD_hvpi25_HVD_HVPI_2025_1.csv",
                date_candidates=("C-VPIZR-0", "ZEIT", "TIME", "TIME_PERIOD"),
                value_candidates=("F-VPIMZBM", "VALUE"),
            )
        raise ValueError(f"Unsupported Statistik Austria dataset: {dataset_id}")
