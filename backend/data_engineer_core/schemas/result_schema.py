from typing import Any, Literal

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: str
    region: str
    metric: str
    value: float
    unit: str | None = None
    source: str
    dataset_id: str


class QueryMetadata(BaseModel):
    granularity_match: Literal["exact", "proxy", "unsupported"] | None = None
    limitations: list[str] = []
    sources: list[str] = []


class QueryResponse(BaseModel):
    status: Literal["success", "partial", "no_data", "auth_required", "error"]
    interpreted_request: dict[str, Any]
    source_plan: dict[str, Any]
    data: list[TimeSeriesPoint] = []
    metadata: QueryMetadata
    warnings: list[str] = []
    errors: list[str] = []
