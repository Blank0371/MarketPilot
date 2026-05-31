from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import requests

from backend.data_engineer_core.schemas.result_schema import TimeSeriesPoint


@dataclass(frozen=True)
class CommoditySeries:
    key: str
    ticker: str
    aliases: tuple[str, ...]
    unit: str
    category: str


class CommodityConnector:
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    SUPPORTED_SERIES: tuple[CommoditySeries, ...] = (
        # Energy
        CommoditySeries("brent", "BZ=F", ("brent", "brent crude"), "usd", "energy"),
        CommoditySeries("wti", "CL=F", ("wti", "west texas", "crude oil"), "usd", "energy"),
        CommoditySeries("natural_gas", "NG=F", ("natural gas", "henry hub", "gas"), "usd", "energy"),
        CommoditySeries("gasoline", "RB=F", ("gasoline", "rbob"), "usd", "energy"),
        CommoditySeries("heating_oil", "HO=F", ("heating oil", "diesel"), "usd", "energy"),
        # Metals
        CommoditySeries("gold", "GC=F", ("gold",), "usd", "metals"),
        CommoditySeries("silver", "SI=F", ("silver",), "usd", "metals"),
        CommoditySeries("copper", "HG=F", ("copper",), "usd", "metals"),
        CommoditySeries("platinum", "PL=F", ("platinum",), "usd", "metals"),
        CommoditySeries("palladium", "PA=F", ("palladium",), "usd", "metals"),
        # Agriculture / fruits / softs
        CommoditySeries("wheat", "ZW=F", ("wheat",), "usd", "agriculture"),
        CommoditySeries("corn", "ZC=F", ("corn", "maize"), "usd", "agriculture"),
        CommoditySeries("soybeans", "ZS=F", ("soybean", "soybeans"), "usd", "agriculture"),
        CommoditySeries("coffee", "KC=F", ("coffee",), "usd", "agriculture"),
        CommoditySeries("sugar", "SB=F", ("sugar",), "usd", "agriculture"),
        CommoditySeries("cocoa", "CC=F", ("cocoa",), "usd", "agriculture"),
        CommoditySeries("cotton", "CT=F", ("cotton",), "usd", "agriculture"),
        CommoditySeries("orange_juice", "OJ=F", ("orange", "orange juice", "fruit"), "usd", "agriculture"),
        # Livestock / supply proxies
        CommoditySeries("lean_hogs", "HE=F", ("lean hog", "hogs", "pork"), "usd", "livestock"),
        CommoditySeries("live_cattle", "LE=F", ("cattle", "beef"), "usd", "livestock"),
        CommoditySeries("freight_shipping_proxy", "BDRY", ("freight", "shipping", "supply chain", "logistics"), "usd", "logistics"),
        CommoditySeries("rare_earth_proxy", "REMX", ("rare earth", "critical minerals"), "usd", "materials"),
    )

    def fetch_timeseries(self, raw_query: str, last_years: int | None) -> list[TimeSeriesPoint]:
        selected = self._select_series(raw_query.lower())
        if selected is None:
            return []

        years = max(1, min(last_years or 10, 30))
        payload = self._fetch_chart(selected.ticker, years)

        result = payload.get("chart", {}).get("result", [])
        if not result:
            return []
        node = result[0]
        timestamps = node.get("timestamp", [])
        closes = node.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        if not timestamps or not closes:
            return []

        points: list[TimeSeriesPoint] = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            points.append(
                TimeSeriesPoint(
                    date=dt.strftime("%Y-%m"),
                    region="Global",
                    metric=f"commodity_price:{selected.key}",
                    value=float(close),
                    unit=selected.unit,
                    source="YahooFinance",
                    dataset_id="yahoo_finance_commodities_monthly",
                )
            )
        return points

    def _fetch_chart(self, ticker: str, years: int) -> dict:
        params = {"interval": "1mo", "range": f"{years}y", "includeAdjustedClose": "true"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
        }
        url = f"{self.BASE_URL}/{ticker}"
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _select_series(self, raw_query: str) -> CommoditySeries | None:
        for series in self.SUPPORTED_SERIES:
            if any(alias in raw_query for alias in series.aliases):
                return series
        return None
