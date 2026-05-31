from backend.data_engineer_core.registry.loader import RegistryLoader
from backend.data_engineer_core.schemas.plan_schema import RejectedCandidate, SourceCandidate, SourcePlan
from backend.data_engineer_core.schemas.request_schema import UserDataRequest


class SourcePlanner:
    def __init__(self, loader: RegistryLoader) -> None:
        self.loader = loader

    def plan(self, request: UserDataRequest) -> SourcePlan:
        if request.output_type != "timeseries":
            return SourcePlan(
                status="no_data",
                selected_candidates=[],
                limitations=["unsupported_output_type: geospatial is out of MVP v1 scope"],
            )

        datasets = self.loader.find_datasets(request.domain, request.metric)
        if not datasets:
            return SourcePlan(status="no_data", selected_candidates=[], limitations=["no_verified_dataset"])

        selected: list[SourceCandidate] = []
        rejected: list[RejectedCandidate] = []

        for dataset in datasets:
            source = self.loader.get_source(dataset.source_id)
            score = 0
            missing: list[str] = []

            if dataset.domain == request.domain:
                score += 40
            if request.metric in dataset.metrics:
                score += 30
            if dataset.time_series:
                score += 20

            if request.geo.districts:
                if dataset.supports_vienna_districts:
                    score += 20
                else:
                    score -= 30
                    missing.append("vienna_district")

            if source.auth_required or source.access != "public":
                rejected.append(
                    RejectedCandidate(source_id=source.id, dataset_id=dataset.id, reason="not_free_source")
                )
                continue

            selected.append(
                SourceCandidate(
                    source_id=source.id,
                    dataset_id=dataset.id,
                    match_score=score,
                    missing_dimensions=missing,
                    reason="candidate_selected",
                )
            )

        selected = sorted(selected, key=lambda x: x.match_score, reverse=True)
        if not selected and rejected:
            return SourcePlan(
                status="no_data",
                selected_candidates=[],
                rejected_candidates=rejected,
                limitations=["no_free_source_available_for_request"],
            )
        if not selected:
            return SourcePlan(status="no_data", selected_candidates=[], rejected_candidates=rejected)
        if selected[0].missing_dimensions:
            return SourcePlan(
                status="partial",
                selected_candidates=selected,
                rejected_candidates=rejected,
                limitations=["requested_granularity_not_available"],
            )
        return SourcePlan(status="exact", selected_candidates=selected, rejected_candidates=rejected)
