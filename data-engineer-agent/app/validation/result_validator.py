from app.schemas.plan_schema import SourcePlan
from app.schemas.request_schema import UserDataRequest
from app.schemas.result_schema import QueryMetadata, QueryResponse, TimeSeriesPoint


class ResultValidator:
    def validate(self, raw_result: dict, request: UserDataRequest, plan: SourcePlan) -> QueryResponse:
        if request.output_type != "timeseries":
            return QueryResponse(
                status="no_data",
                interpreted_request=request.model_dump(),
                source_plan=plan.model_dump(),
                data=[],
                metadata=QueryMetadata(
                    granularity_match="unsupported",
                    limitations=["unsupported_output_type: geospatial is out of MVP v1 scope"],
                    sources=[],
                ),
            )

        if plan.status in {"no_data", "auth_required"}:
            api_status = "auth_required" if plan.status == "auth_required" else "no_data"
            return QueryResponse(
                status=api_status,
                interpreted_request=request.model_dump(),
                source_plan=plan.model_dump(),
                data=[],
                metadata=QueryMetadata(
                    granularity_match="unsupported" if plan.status == "no_data" else "exact",
                    limitations=plan.limitations or [plan.status],
                    sources=[],
                ),
            )

        rows = raw_result.get("data", [])
        points = [TimeSeriesPoint.model_validate(row) for row in rows]

        is_proxy = bool(request.geo.districts) and all(point.region.lower() == "vienna" for point in points)
        limitations = list(raw_result.get("metadata", {}).get("limitations", []))

        if is_proxy:
            limitations.append("Requested district-level data was not available; returned city-level proxy")
            status = "partial"
            granularity_match = "proxy"
        else:
            status = "success"
            granularity_match = "exact"

        if plan.status == "partial":
            status = "partial"
            if not limitations:
                limitations = ["requested_granularity_not_available"]
            granularity_match = "proxy"

        if any(item.startswith("insufficient_history:") for item in limitations):
            status = "partial"

        sources = [f"{plan.selected_candidates[0].source_id}:{plan.selected_candidates[0].dataset_id}"]
        return QueryResponse(
            status=status,
            interpreted_request=request.model_dump(),
            source_plan=plan.model_dump(),
            data=points,
            metadata=QueryMetadata(
                granularity_match=granularity_match,
                limitations=limitations,
                sources=sources,
            ),
        )
