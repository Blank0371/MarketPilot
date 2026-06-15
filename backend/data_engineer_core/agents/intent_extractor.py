import re

from data_engineer_core.schemas.request_schema import GeoRequest, TimeRange, UserDataRequest


class IntentExtractor:
    COUNTRY_CODES = {
        "austria": "AT",
        "germany": "DE",
        "france": "FR",
        "italy": "IT",
        "spain": "ES",
        "netherlands": "NL",
        "belgium": "BE",
        "poland": "PL",
        "czechia": "CZ",
        "hungary": "HU",
        "european union": "EU27_2020",
        "eu": "EU27_2020",
    }

    def extract(self, raw_text: str) -> UserDataRequest:
        text = raw_text.lower()
        output_type = (
            "geospatial"
            if any(token in text for token in ["boundary", "boundaries", "district map"])
            else "timeseries"
        )
        metric, domain, unit = self.detect_metric(text)
        city = "Vienna" if any(token in text for token in ["vienna", "wien"]) else None
        country = self.detect_country(text, city)

        districts = self.parse_district_range(text)
        last_years = self.parse_last_years(text)
        frequency_preference = self.detect_frequency(text, metric)

        return UserDataRequest(
            raw_text=raw_text,
            domain=domain,
            metric=metric,
            unit=unit,
            output_type=output_type,
            geo=GeoRequest(country=country, city=city, districts=districts),
            time_range=TimeRange(type="relative", last_years=last_years or 10),
            frequency_preference=frequency_preference,
        )

    @staticmethod
    def detect_metric(text: str) -> tuple[str, str, str | None]:
        rules: list[tuple[str, str, str | None, list[str]]] = [
            (
                "tourism_nights",
                "tourism",
                "nights",
                ["tourism", "tourist", "overnight", "nights", "accommodation", "foot traffic", "festival"],
            ),
            (
                "gross_wages_index",
                "labor",
                "index_2021_100",
                ["wage", "salary", "staff costs", "payroll", "benefits", "gross wages"],
            ),
            (
                "commodity_price",
                "commodities",
                "usd",
                [
                    "commodity",
                    "commodities",
                    "brent",
                    "wti",
                    "natural gas",
                    "henry hub",
                    "gold",
                    "silver",
                    "copper",
                    "aluminum",
                    "aluminium",
                    "wheat",
                    "maize",
                    "corn",
                    "coal",
                ],
            ),
            (
                "unemployment_rate",
                "labor",
                "percent_of_active_population",
                ["unemployment", "jobless rate", "labor market"],
            ),
            (
                "gdp_nominal",
                "economy",
                "million_eur",
                ["gdp", "gross domestic product", "economic output"],
            ),
            (
                "inflation_index",
                "economy",
                "index_2015_100",
                ["inflation", "consumer price", "cpi", "hicp"],
            ),
            (
                "average_rent",
                "housing",
                "eur_per_sqm_per_month",
                ["rent", "rental", "lease", "housing costs"],
            ),
        ]
        for metric, domain, unit, tokens in rules:
            if any(token in text for token in tokens):
                return metric, domain, unit
        return "unknown_metric", "unknown", None

    def detect_country(self, text: str, city: str | None) -> str | None:
        for name, code in self.COUNTRY_CODES.items():
            if name in text:
                return code
        if city == "Vienna":
            return "AT"
        return "AT"

    @staticmethod
    def detect_frequency(text: str, metric: str) -> str:
        if "monthly" in text:
            return "monthly"
        if "quarterly" in text:
            return "quarterly"
        if "yearly" in text or "annual" in text:
            return "annual"
        if metric == "gdp_nominal":
            return "quarterly"
        return "monthly_or_quarterly"

    @staticmethod
    def parse_district_range(text: str) -> list[int] | None:
        if "district" not in text:
            return None

        numbers = [int(item) for item in re.findall(r"\d+", text)]
        if len(numbers) < 2:
            return None

        # Use the first two mentioned district numbers (e.g. "districts 1 to 9").
        start, end = numbers[0], numbers[1]
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    @staticmethod
    def parse_last_years(text: str) -> int | None:
        m = re.search(r"(?:last|past)\s+(\d+)\s*-\s*(\d+)\s+years", text)
        if m:
            low = int(m.group(1))
            high = int(m.group(2))
            return max(low, high)
        m = re.search(r"last\s+(\d+)\s+years", text)
        if m:
            return int(m.group(1))
        m = re.search(r"past\s+(\d+)\s+years", text)
        if m:
            return int(m.group(1))
        m = re.search(r"last\s+(\d+)\s+year", text)
        if m:
            return int(m.group(1))
        return None
