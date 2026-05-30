from app.schemas.plan_schema import SourceCandidate, SourcePlan
from app.schemas.request_schema import GeoRequest, TimeRange, UserDataRequest
from app.validation.result_validator import ResultValidator


def test_validator_forces_partial_for_proxy_granularity() -> None:
    validator = ResultValidator()
    req = UserDataRequest(
        raw_text="...",
        domain="housing",
        metric="average_rent",
        unit="eur_per_sqm_per_month",
        geo=GeoRequest(city="Vienna", districts=[1, 2, 3]),
        time_range=TimeRange(type="relative", last_years=5),
    )
    plan = SourcePlan(
        status="partial",
        selected_candidates=[
            SourceCandidate(
                source_id="eurostat",
                dataset_id="eurostat_city_rents",
                match_score=60,
                missing_dimensions=["vienna_district"],
                reason="candidate_selected",
            )
        ],
    )
    raw = {
        "data": [
            {
                "date": "2024-Q1",
                "region": "Vienna",
                "metric": "average_rent",
                "value": 10.0,
                "unit": "eur_per_sqm_per_month",
                "source": "eurostat",
                "dataset_id": "eurostat_city_rents",
            }
        ],
        "metadata": {"limitations": []},
    }
    result = validator.validate(raw, req, plan)
    assert result.status == "partial"
    assert result.metadata.granularity_match == "proxy"
