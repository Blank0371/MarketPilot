from app.adapters.commodities import CommodityConnector


def test_select_series_from_query() -> None:
    connector = CommodityConnector()
    series = connector._select_series("get brent commodity prices for the last 10 years")
    assert series is not None
    assert series.key == "brent"
    assert series.ticker == "BZ=F"


def test_select_series_for_fruit_and_metals() -> None:
    connector = CommodityConnector()
    fruit = connector._select_series("show orange juice prices for the last 10 years")
    metal = connector._select_series("get copper prices")
    assert fruit is not None and fruit.ticker == "OJ=F"
    assert metal is not None and metal.ticker == "HG=F"
