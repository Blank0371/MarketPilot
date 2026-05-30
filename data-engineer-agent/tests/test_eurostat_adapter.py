from app.adapters.eurostat import EurostatAdapter


def test_supported_dataset_configs() -> None:
    adapter = EurostatAdapter()
    cfg1 = adapter._config_for_dataset("eurostat_hicp_all_items", "AT")
    assert cfg1.dataset_code == "prc_hicp_midx"
    assert cfg1.params["coicop"] == "CP00"

    cfg2 = adapter._config_for_dataset("eurostat_unemployment_rate", "DE")
    assert cfg2.dataset_code == "une_rt_m"
    assert cfg2.params["geo"] == "DE"

    cfg3 = adapter._config_for_dataset("eurostat_gdp_nominal_quarterly", "AT")
    assert cfg3.dataset_code == "namq_10_gdp"
    assert cfg3.params["na_item"] == "B1GQ"
