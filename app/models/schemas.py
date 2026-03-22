from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class EmploymentTypeEnum(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"
    other = "other"


class SeniorityLevelEnum(str, Enum):
    intern = "intern"
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    manager = "manager"
    director = "director"
    executive = "executive"
    unknown = "unknown"


class RemoteTypeEnum(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"


class ErrorInfo(BaseModel):
    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: list[str] | None = Field(default=None, description="Optional list of human-readable error details.")


class ErrorEnvelope(BaseModel):
    request_id: str
    timestamp: datetime
    data: None = None
    error: ErrorInfo


class HealthData(BaseModel):
    status: str
    service: str
    version: str
    database: str


class HealthEnvelope(BaseModel):
    request_id: str
    timestamp: datetime
    data: HealthData
    error: ErrorInfo | None = None


class RawJobListing(BaseModel):
    source: str | None = None
    source_job_id: str | None = None
    source_job_url: str | None = None
    title: str | None = None
    company: str | None = None
    location_raw: str | None = None
    salary_text: str | None = None
    description_text: str | None = None
    tags: list[str] = Field(default_factory=list)
    posted_at_raw: str | None = None
    employment_type_raw: str | None = None
    remote_type_raw: str | None = None


class JobRecord(BaseModel):
    id: str
    source: str
    source_job_id: str | None = None
    source_job_url: HttpUrl | None = None
    title: str | None = None
    normalized_title: str | None = None
    company: str | None = None
    location_raw: str | None = None
    location_city: str | None = None
    location_country: str | None = None
    remote_type: RemoteTypeEnum | None = None
    employment_type: EmploymentTypeEnum | None = None
    seniority_level: SeniorityLevelEnum | None = None
    salary_text: str | None = None
    description_snippet: str | None = None
    skills: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    freshness_days: int | None = None


class SearchFilters(BaseModel):
    location: str | None = None
    remote: bool | None = None
    employment_type: EmploymentTypeEnum | None = None
    seniority: SeniorityLevelEnum | None = None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total_pages: int
    total_results: int


class JobSearchData(BaseModel):
    query: str | None = None
    filters: SearchFilters
    pagination: PaginationMeta
    count: int
    jobs: list[JobRecord]


class JobSearchEnvelope(BaseModel):
    request_id: str
    timestamp: datetime
    data: JobSearchData
    error: ErrorInfo | None = None


class JobDetailData(BaseModel):
    job: JobRecord


class JobDetailEnvelope(BaseModel):
    request_id: str
    timestamp: datetime
    data: JobDetailData
    error: ErrorInfo | None = None


class InsightItem(BaseModel):
    name: str
    count: int


class InsightsData(BaseModel):
    dimension: str
    count: int
    items: list[InsightItem]


class InsightsEnvelope(BaseModel):
    request_id: str
    timestamp: datetime
    data: InsightsData
    error: ErrorInfo | None = None
