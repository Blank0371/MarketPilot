from fastapi import FastAPI

from backend.data_engineer_core.adapters.commodities import CommodityConnector
from backend.data_engineer_core.adapters.eurostat import EurostatAdapter
from backend.data_engineer_core.agents.code_planner import CodePlanner
from backend.data_engineer_core.agents.intent_extractor import IntentExtractor
from backend.data_engineer_core.agents.source_planner import SourcePlanner
from backend.data_engineer_core.config import settings
from backend.data_engineer_core.registry.loader import RegistryLoader
from backend.data_engineer_core.sandbox.runner import SandboxRunner
from backend.data_engineer_core.schemas.request_schema import QueryInput
from backend.data_engineer_core.schemas.result_schema import QueryMetadata, QueryResponse
from backend.data_engineer_core.validation.result_validator import ResultValidator

app = FastAPI(title="Data Engineer Agent", version="0.1.0")

loader = RegistryLoader(settings.sources_path, settings.datasets_path)
intent_extractor = IntentExtractor()
source_planner = SourcePlanner(loader)
code_planner = CodePlanner()
sandbox_runner = SandboxRunner()
validator = ResultValidator()
eurostat_adapter = EurostatAdapter()
commodity_connector = CommodityConnector()


def _coverage_years(points: list[dict]) -> int:
    years: list[int] = []
    for point in points:
        label = point.get("date", "")
        digits = "".join(ch for ch in label if ch.isdigit())
        if len(digits) >= 4:
            years.append(int(digits[:4]))
    if not years:
        return 0
    return max(years) - min(years) + 1


@app.post("/dry-run", response_model=QueryResponse)
def dry_run(payload: QueryInput) -> QueryResponse:
    interpreted = intent_extractor.extract(payload.query)
    plan = source_planner.plan(interpreted)

    status = "auth_required" if plan.status == "auth_required" else "no_data" if plan.status == "no_data" else "partial" if plan.status == "partial" else "success"
    return QueryResponse(
        status=status,
        interpreted_request=interpreted.model_dump(),
        source_plan=plan.model_dump(),
        data=[],
        metadata=QueryMetadata(
            granularity_match="proxy" if plan.status == "partial" else "exact",
            limitations=plan.limitations,
            sources=[],
        ),
    )


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryInput) -> QueryResponse:
    interpreted = intent_extractor.extract(payload.query)
    plan = source_planner.plan(interpreted)

    if plan.status in {"no_data", "auth_required"} or not plan.selected_candidates:
        return validator.validate({}, interpreted, plan)

    top_candidate = plan.selected_candidates[0]
    raw_result: dict
    if top_candidate.source_id == "eurostat":
        try:
            points = eurostat_adapter.fetch_timeseries(
                dataset_id=top_candidate.dataset_id,
                metric=interpreted.metric,
                last_years=interpreted.time_range.last_years,
                geo_code=interpreted.geo.country,
            )
        except Exception as exc:
            return QueryResponse(
                status="error",
                interpreted_request=interpreted.model_dump(),
                source_plan=plan.model_dump(),
                data=[],
                metadata=QueryMetadata(
                    granularity_match="unsupported",
                    limitations=["source_fetch_failed"],
                    sources=[],
                ),
                errors=[str(exc)],
            )
        raw_result = {"status": "success", "data": [item.model_dump() for item in points], "metadata": {"limitations": []}}
    elif top_candidate.source_id == "yahoo_finance_commodities":
        try:
            points = commodity_connector.fetch_timeseries(
                raw_query=interpreted.raw_text,
                last_years=interpreted.time_range.last_years,
            )
        except Exception as exc:
            return QueryResponse(
                status="error",
                interpreted_request=interpreted.model_dump(),
                source_plan=plan.model_dump(),
                data=[],
                metadata=QueryMetadata(
                    granularity_match="unsupported",
                    limitations=["source_fetch_failed"],
                    sources=[],
                ),
                errors=[str(exc)],
            )
        raw_result = {
            "status": "success",
            "data": [item.model_dump() for item in points],
            "metadata": {"limitations": []},
        }
    else:
        script = code_planner.build_script(plan, interpreted)
        execution = sandbox_runner.run(script)
        if execution.exit_code != 0:
            return QueryResponse(
                status="error",
                interpreted_request=interpreted.model_dump(),
                source_plan=plan.model_dump(),
                data=[],
                metadata=QueryMetadata(
                    granularity_match="unsupported",
                    limitations=["execution_failed"],
                    sources=[],
                ),
                errors=[execution.stderr or "sandbox execution failed"],
            )
        raw_result = execution.result_json

    if not raw_result.get("data"):
        return QueryResponse(
            status="no_data",
            interpreted_request=interpreted.model_dump(),
            source_plan=plan.model_dump(),
            data=[],
            metadata=QueryMetadata(
                granularity_match="unsupported",
                limitations=["no_observations_returned_from_source"],
                sources=[f"{top_candidate.source_id}:{top_candidate.dataset_id}"],
            ),
        )

    requested_years = interpreted.time_range.last_years or 10
    coverage = _coverage_years(raw_result["data"])
    if coverage < min(5, requested_years):
        raw_result["metadata"]["limitations"].append(
            f"insufficient_history: requested up to {requested_years} years, got about {coverage} years"
        )

    return validator.validate(raw_result, interpreted, plan)


@app.get("/sources")
def sources() -> list[dict]:
    return [item.model_dump() for item in loader.load_sources()]


@app.get("/datasets")
def datasets() -> list[dict]:
    return [item.model_dump() for item in loader.load_datasets()]
