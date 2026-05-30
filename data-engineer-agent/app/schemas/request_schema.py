from typing import Literal

from pydantic import BaseModel, Field


class GeoRequest(BaseModel):
    country: str | None = None
    city: str | None = None
    districts: list[int] | None = None
    region: str | None = None


class TimeRange(BaseModel):
    type: Literal["relative", "absolute"] = "relative"
    last_years: int | None = Field(default=None, ge=1, le=30)
    start_date: str | None = None
    end_date: str | None = None


class UserDataRequest(BaseModel):
    raw_text: str
    domain: str
    metric: str
    unit: str | None = None
    output_type: Literal["timeseries", "geospatial"] = "timeseries"
    geo: GeoRequest
    time_range: TimeRange
    frequency_preference: str | None = None
    required_output: Literal["timeseries"] = "timeseries"


class QueryInput(BaseModel):
    query: str
