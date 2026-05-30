from app.agents.intent_extractor import IntentExtractor


def test_extract_district_range_and_years() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("average rent per square meter in Vienna districts 1 to 9 for the last 5 years")
    assert req.geo.districts == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert req.time_range.last_years == 5
    assert req.metric == "average_rent"


def test_extract_inflation_metric() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("Get CPI inflation in Austria for the past 3 years")
    assert req.metric == "inflation_index"
    assert req.domain == "economy"
    assert req.geo.country == "AT"
    assert req.time_range.last_years == 3


def test_extract_unemployment_metric() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("Show unemployment rate in Germany for the last 2 years")
    assert req.metric == "unemployment_rate"
    assert req.domain == "labor"
    assert req.geo.country == "DE"


def test_extract_year_range_uses_upper_bound() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("Get inflation in Austria for the last 5-10 years")
    assert req.time_range.last_years == 10


def test_default_horizon_is_ten_years() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("Get GDP in Austria")
    assert req.time_range.last_years == 10


def test_extract_commodity_metric() -> None:
    extractor = IntentExtractor()
    req = extractor.extract("Get Brent commodity prices for the last 10 years")
    assert req.metric == "commodity_price"
    assert req.domain == "commodities"
