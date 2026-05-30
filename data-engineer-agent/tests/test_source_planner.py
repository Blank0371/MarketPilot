from app.agents.source_planner import SourcePlanner
from app.config import settings
from app.registry.loader import RegistryLoader
from app.schemas.request_schema import GeoRequest, TimeRange, UserDataRequest


def test_vienna_rent_is_partial() -> None:
    loader = RegistryLoader(settings.sources_path, settings.datasets_path)
    planner = SourcePlanner(loader)

    req = UserDataRequest(
        raw_text="...",
        domain="housing",
        metric="average_rent",
        unit="eur_per_sqm_per_month",
        geo=GeoRequest(city="Vienna", districts=[1, 2, 3]),
        time_range=TimeRange(type="relative", last_years=5),
    )
    plan = planner.plan(req)
    assert plan.status == "partial"
    assert "vienna_district" in plan.selected_candidates[0].missing_dimensions


def test_paid_sources_are_excluded() -> None:
    loader = RegistryLoader(settings.sources_path, settings.datasets_path)
    planner = SourcePlanner(loader)

    req = UserDataRequest(
        raw_text="...",
        domain="housing",
        metric="average_rent",
        unit="eur_per_sqm_per_month",
        geo=GeoRequest(city="Vienna"),
        time_range=TimeRange(type="relative", last_years=5),
    )
    plan = planner.plan(req)
    assert all(item.reason != "auth_required" for item in plan.rejected_candidates)
    assert any(item.reason == "not_free_source" for item in plan.rejected_candidates)


def test_gdp_query_has_public_candidate() -> None:
    loader = RegistryLoader(settings.sources_path, settings.datasets_path)
    planner = SourcePlanner(loader)

    req = UserDataRequest(
        raw_text="...",
        domain="economy",
        metric="gdp_nominal",
        geo=GeoRequest(country="AT"),
        time_range=TimeRange(type="relative", last_years=5),
    )
    plan = planner.plan(req)
    assert plan.status in {"exact", "partial"}
    assert any(c.dataset_id == "eurostat_gdp_nominal_quarterly" for c in plan.selected_candidates)


def test_commodity_query_has_yahoo_candidate() -> None:
    loader = RegistryLoader(settings.sources_path, settings.datasets_path)
    planner = SourcePlanner(loader)

    req = UserDataRequest(
        raw_text="...",
        domain="commodities",
        metric="commodity_price",
        geo=GeoRequest(country="AT"),
        time_range=TimeRange(type="relative", last_years=10),
    )
    plan = planner.plan(req)
    assert plan.status in {"exact", "partial"}
    assert any(c.dataset_id == "yahoo_finance_commodities_monthly" for c in plan.selected_candidates)
