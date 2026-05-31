from pydantic import BaseModel


class SourceDefinition(BaseModel):
    id: str
    name: str
    type: str
    base_url: str
    access: str
    auth_required: bool
    formats: list[str]
    domains: list[str]


class DatasetDefinition(BaseModel):
    id: str
    source_id: str
    title: str
    verified: bool
    domain: str
    metrics: list[str]
    time_series: bool
    geo_granularity: list[str]
    supports_vienna_districts: bool | None = None
    access: dict | None = None
    limitations: list[str] = []
