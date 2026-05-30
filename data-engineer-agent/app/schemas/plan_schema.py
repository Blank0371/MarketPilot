from typing import Literal

from pydantic import BaseModel


class SourceCandidate(BaseModel):
    source_id: str
    dataset_id: str
    match_score: int
    missing_dimensions: list[str]
    reason: str


class RejectedCandidate(BaseModel):
    source_id: str
    dataset_id: str
    reason: str


class SourcePlan(BaseModel):
    status: Literal["exact", "partial", "no_data", "auth_required", "error"]
    selected_candidates: list[SourceCandidate]
    rejected_candidates: list[RejectedCandidate] = []
    limitations: list[str] = []
