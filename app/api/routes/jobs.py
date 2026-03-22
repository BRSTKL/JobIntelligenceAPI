from __future__ import annotations

import logging
import math
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Body, Path, Query, Request, Security
from pydantic import ValidationError

from app.api.docs import (
    AI_CONFIGURATION_ERROR_EXAMPLE,
    AI_PROVIDER_ERROR_EXAMPLE,
    AI_RESPONSE_ERROR_EXAMPLE,
    AUTH_ERROR_RESPONSES,
    INTERNAL_ERROR_EXAMPLE,
    RATE_LIMIT_EXAMPLE,
    UPSTREAM_ERROR_EXAMPLE,
    VALIDATION_ERROR_EXAMPLE,
    error_response_doc,
)
from app.core.auth import require_api_key
from app.core.exceptions import AIResponseError, NotFoundError, UpstreamSourceError
from app.core.responses import build_response_metadata
from app.models.schemas import (
    EmploymentTypeEnum,
    JobDetailData,
    JobDetailEnvelope,
    JobMatchData,
    JobMatchEnvelope,
    JobMatchRequest,
    JobRecord,
    RawJobListing,
    JobSearchData,
    JobSearchEnvelope,
    MatchedJob,
    PaginationMeta,
    RemoteTypeEnum,
    SearchFilters,
    SeniorityLevelEnum,
    SkillsGapData,
    SkillsGapEnvelope,
    SkillsGapRequest,
    SkillsGapResult,
)


logger = logging.getLogger(__name__)

SEARCH_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5100",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "query": "python",
        "filters": {
            "country": None,
            "location": None,
            "remote": True,
            "employment_type": "full_time",
            "seniority": "senior",
        },
        "pagination": {
            "page": 1,
            "limit": 10,
            "total_pages": 1,
            "total_results": 1,
        },
        "count": 1,
        "jobs": [
            {
                "id": "8eb5a31de77f3c2a3fbb3f69",
                "source": "arbeitnow",
                "source_job_id": "1001",
                "source_job_url": "https://www.arbeitnow.com/jobs/1001",
                "language": "en",
                "title": "Senior Python Backend Engineer",
                "normalized_title": "Python Backend Engineer",
                "company": "Acme",
                "location_raw": "Berlin, Germany",
                "location_city": "Berlin",
                "location_country": "Germany",
                "remote_type": "remote",
                "employment_type": "full_time",
                "seniority_level": "senior",
                "salary_text": "$100k - $120k",
                "description_snippet": "Build FastAPI services with Python, Docker, and AWS.",
                "skills": ["aws", "docker", "fastapi", "python"],
                "posted_at": "2026-03-20T10:00:00Z",
                "freshness_days": 2,
            }
        ],
    },
    "error": None,
}

JOB_DETAIL_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5101",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "job": SEARCH_SUCCESS_EXAMPLE["data"]["jobs"][0],
    },
    "error": None,
}

JOB_NOT_FOUND_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5102",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "not_found",
        "message": "Job 'missing-job-id' was not found.",
        "details": ["job_id=missing-job-id"],
    },
}

JOB_MATCH_REQUEST_EXAMPLE = {
    "skills": ["python", "fastapi", "docker"],
    "experience_years": 3,
    "preferred_location": "Istanbul",
    "remote_preferred": True,
}

JOB_MATCH_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5103",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "skills": ["python", "fastapi", "docker"],
        "experience_years": 3,
        "preferred_location": "Istanbul",
        "remote_preferred": True,
        "count": 1,
        "matches": [
            {
                "job": SEARCH_SUCCESS_EXAMPLE["data"]["jobs"][0],
                "match_score": 100,
            }
        ],
    },
    "error": None,
}

SKILLS_GAP_REQUEST_EXAMPLE = {
    "current_skills": ["python", "django"],
    "target_job_title": "Senior DevOps Engineer",
}

SKILLS_GAP_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5104",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "current_skills": ["python", "django"],
        "target_job_title": "Senior DevOps Engineer",
        "analysis": {
            "missing_skills": ["kubernetes", "terraform"],
            "learning_priority": "high",
            "estimated_learning_time": "3-6 months",
            "recommended_resources": ["resource1", "resource2"],
        },
    },
    "error": None,
}

router = APIRouter(prefix="/jobs", tags=["Jobs"], dependencies=[Security(require_api_key)])


def _canonicalize_url(value: str | None) -> str | None:
    """Build a simple canonical form so the same URL can be deduplicated reliably."""
    if not value:
        return None

    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip().rstrip("/").lower()

    normalized_path = parsed.path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            parsed.query,
            "",
        )
    )


def _deduplicate_raw_jobs(raw_jobs: list[RawJobListing]) -> list[RawJobListing]:
    """Keep the first job seen for each source URL and preserve source-order precedence."""
    deduplicated_jobs: list[RawJobListing] = []
    seen_urls: set[str] = set()

    for raw_job in raw_jobs:
        canonical_url = _canonicalize_url(raw_job.source_job_url)
        if canonical_url:
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)

        deduplicated_jobs.append(raw_job)

    return deduplicated_jobs


def _cache_key(
    query: str | None,
    country: str | None,
    location: str | None,
    remote: bool | None,
    employment_type: EmploymentTypeEnum | None,
    seniority: SeniorityLevelEnum | None,
) -> str:
    # The cache stores the normalized result set for a logical search, not a page slice.
    parts = [
        (query or "").strip().lower(),
        (country or "").strip().lower(),
        (location or "").strip().lower(),
        str(remote),
        employment_type.value if employment_type else "",
        seniority.value if seniority else "",
    ]
    return "|".join(parts)


def _matches_query(job: JobRecord, query: str | None) -> bool:
    if not query:
        return True

    haystack = " ".join(
        filter(
            None,
            [
                job.title,
                job.normalized_title,
                job.company,
                job.description_snippet,
                " ".join(job.skills),
            ],
        )
    ).lower()
    return query.lower() in haystack


def _matches_location(job: JobRecord, location: str | None) -> bool:
    if not location:
        return True

    haystack = " ".join(filter(None, [job.location_raw, job.location_city, job.location_country])).lower()
    return location.lower() in haystack


def _matches_country(job: JobRecord, country: str | None) -> bool:
    if not country:
        return True

    haystack = " ".join(filter(None, [job.location_raw, job.location_city, job.location_country])).lower()
    cleaned_country = country.strip().lower()

    if cleaned_country == "tr":
        turkish_keywords = (
            "turkey",
            "turkiye",
            "türkiye",
            "istanbul",
            "i̇stanbul",
            "ankara",
            "izmir",
            "i̇zmir",
            " tr ",
        )
        normalized_haystack = f" {haystack} "
        return any(keyword in normalized_haystack for keyword in turkish_keywords)

    return cleaned_country in haystack


def _matches_remote(job: JobRecord, remote: bool | None) -> bool:
    if remote is None:
        return True
    if remote:
        return job.remote_type in {RemoteTypeEnum.remote, RemoteTypeEnum.hybrid}
    return job.remote_type == RemoteTypeEnum.onsite


def _filter_jobs(
    jobs: list[JobRecord],
    query: str | None,
    country: str | None,
    location: str | None,
    remote: bool | None,
    employment_type: EmploymentTypeEnum | None,
    seniority: SeniorityLevelEnum | None,
) -> list[JobRecord]:
    filtered_jobs = []
    for job in jobs:
        if not _matches_query(job, query):
            continue
        if not _matches_country(job, country):
            continue
        if not _matches_location(job, location):
            continue
        if not _matches_remote(job, remote):
            continue
        if employment_type is not None and job.employment_type != employment_type:
            continue
        if seniority is not None and job.seniority_level != seniority:
            continue
        filtered_jobs.append(job)

    return sorted(
        filtered_jobs,
        key=lambda job: (
            job.freshness_days is None,
            job.freshness_days if job.freshness_days is not None else 10_000,
            (job.title or "").lower(),
        ),
    )


def _unique_job_ids(job_ids: list[str], valid_ids: set[str], limit: int = 5) -> list[str]:
    """Keep valid Gemini job IDs unique and ordered."""
    unique_ids: list[str] = []
    seen_ids: set[str] = set()

    for job_id in job_ids:
        if job_id not in valid_ids or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        unique_ids.append(job_id)
        if len(unique_ids) >= limit:
            break

    return unique_ids


def _match_score_for_rank(rank: int) -> int:
    """Map ranked Gemini matches onto a simple 1-100 score scale."""
    return max(100 - (rank * 10), 10)


@router.get(
    "/search",
    response_model=JobSearchEnvelope,
    summary="Search structured job data",
    description=(
        "Fetch public job listings from multiple sources, normalize them into consistent records, "
        "persist deduplicated results, and return paginated job data for search, matching, or "
        "analytics experiences."
    ),
    response_description="Standard success envelope containing paginated job search results.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Search results returned successfully.",
            "content": {
                "application/json": {
                    "example": SEARCH_SUCCESS_EXAMPLE,
                }
            },
        },
        422: error_response_doc("Request validation failed.", VALIDATION_ERROR_EXAMPLE),
        502: error_response_doc("Upstream job source request failed.", UPSTREAM_ERROR_EXAMPLE),
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
async def search_jobs(
    request: Request,
    q: str | None = Query(
        default=None,
        description="Optional free-text query matched against job title, company, description snippet, and extracted skills.",
    ),
    country: str | None = Query(
        default=None,
        description="Optional country filter. Use TR to keep Turkey-related jobs by matching Turkey, Türkiye, Istanbul, Ankara, Izmir, or TR in the stored location fields.",
    ),
    location: str | None = Query(default=None, description="Optional free-text location filter."),
    page: int = Query(default=1, ge=1, description="1-based page number for paginated results."),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=50,
        description="Number of jobs to return per page. Defaults to the configured page size.",
    ),
    remote: bool | None = Query(
        default=None,
        description="When true, keep remote or hybrid jobs. When false, keep only onsite jobs.",
    ),
    employment_type: EmploymentTypeEnum | None = Query(
        default=None,
        description="Optional normalized employment type filter.",
    ),
    seniority: SeniorityLevelEnum | None = Query(
        default=None,
        description="Optional normalized seniority filter.",
    ),
) -> JobSearchEnvelope:
    settings = request.app.state.settings
    cache = request.app.state.cache
    fetcher = request.app.state.fetcher
    parser = request.app.state.parser
    normalizer = request.app.state.normalizer
    repository = request.app.state.repository

    filters = SearchFilters(
        country=country,
        location=location,
        remote=remote,
        employment_type=employment_type,
        seniority=seniority,
    )

    search_key = _cache_key(q, country, location, remote, employment_type, seniority)
    normalized_jobs = cache.get(search_key)

    if normalized_jobs is None:
        logger.info("Cache miss for search key '%s'", search_key)
        try:
            source_payloads = await fetcher.fetch_source_payloads(q)
        except httpx.HTTPError as exc:
            logger.exception("Failed to fetch public job listings from all configured sources")
            raise UpstreamSourceError("Failed to fetch public job listings from the configured sources.") from exc

        # Split each successful source payload into raw records, then normalize them into the API shape.
        raw_jobs = parser.parse_source_payloads(source_payloads)
        raw_jobs = _deduplicate_raw_jobs(raw_jobs)
        normalized_jobs = normalizer.normalize_jobs(raw_jobs)
        normalized_jobs = repository.upsert_jobs(normalized_jobs)
        cache.set(search_key, normalized_jobs)
    else:
        logger.info("Cache hit for search key '%s'", search_key)

    filtered_jobs = _filter_jobs(
        normalized_jobs,
        query=q,
        country=country,
        location=location,
        remote=remote,
        employment_type=employment_type,
        seniority=seniority,
    )

    page_size = min(limit or settings.default_page_size, settings.max_page_size)
    total_results = len(filtered_jobs)
    total_pages = max(math.ceil(total_results / page_size), 1)
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    jobs_page = filtered_jobs[start_index:end_index]

    return JobSearchEnvelope(
        **build_response_metadata(request),
        data=JobSearchData(
            query=q,
            filters=filters,
            pagination=PaginationMeta(
                page=page,
                limit=page_size,
                total_pages=total_pages,
                total_results=total_results,
            ),
            count=len(jobs_page),
            jobs=jobs_page,
        ),
        error=None,
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailEnvelope,
    summary="Get one job record by ID",
    description=(
        "Return one stored job record from the local SQLite database using the internal job ID. "
        "Useful for detail pages, matching flows, and analytics drill-downs."
    ),
    response_description="Standard success envelope containing one normalized job record.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Job record returned successfully.",
            "content": {
                "application/json": {
                    "example": JOB_DETAIL_SUCCESS_EXAMPLE,
                }
            },
        },
        404: error_response_doc("Requested job was not found.", JOB_NOT_FOUND_EXAMPLE),
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def get_job(
    request: Request,
    job_id: str = Path(description="Internal job identifier returned by the search endpoint."),
) -> JobDetailEnvelope:
    repository = request.app.state.repository
    job = repository.get_job(job_id)
    if job is None:
        raise NotFoundError(message=f"Job '{job_id}' was not found.", details=[f"job_id={job_id}"])

    return JobDetailEnvelope(
        **build_response_metadata(request),
        data=JobDetailData(job=job),
        error=None,
    )


@router.post(
    "/match",
    response_model=JobMatchEnvelope,
    summary="Match a candidate profile to stored jobs",
    description=(
        "Read recent jobs from the local database, ask Gemini for the best matching job IDs, "
        "and return the top matches with a simple rank-based match score."
    ),
    response_description="Standard success envelope containing matched jobs and scores.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {"description": "Job matches returned successfully.", "content": {"application/json": {"example": JOB_MATCH_SUCCESS_EXAMPLE}}},
        422: error_response_doc("Request validation failed.", VALIDATION_ERROR_EXAMPLE),
        429: error_response_doc("AI endpoint rate limit exceeded.", RATE_LIMIT_EXAMPLE),
        502: error_response_doc("Gemini request failed or returned invalid JSON.", AI_PROVIDER_ERROR_EXAMPLE),
        503: error_response_doc("Gemini is not configured.", AI_CONFIGURATION_ERROR_EXAMPLE),
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def match_jobs(
    request: Request,
    payload: JobMatchRequest = Body(
        openapi_examples={"default": {"summary": "Candidate profile", "value": JOB_MATCH_REQUEST_EXAMPLE}}
    ),
) -> JobMatchEnvelope:
    repository = request.app.state.repository
    gemini_client = request.app.state.gemini_client
    ai_rate_limiter = request.app.state.ai_rate_limiter
    api_key = getattr(request.state, "api_key", None)

    if api_key:
        ai_rate_limiter.enforce(api_key)

    recent_jobs = repository.list_recent_jobs(limit=100)
    if not recent_jobs:
        return JobMatchEnvelope(
            **build_response_metadata(request),
            data=JobMatchData(
                skills=payload.skills,
                experience_years=payload.experience_years,
                preferred_location=payload.preferred_location,
                remote_preferred=payload.remote_preferred,
                count=0,
                matches=[],
            ),
            error=None,
        )

    returned_ids = gemini_client.match_jobs(
        skills=payload.skills,
        experience_years=payload.experience_years,
        preferred_location=payload.preferred_location,
        remote_preferred=payload.remote_preferred,
        jobs=recent_jobs,
    )
    jobs_by_id = {job.id: job for job in recent_jobs}
    ranked_ids = _unique_job_ids(returned_ids, set(jobs_by_id))
    matches = [
        MatchedJob(job=jobs_by_id[job_id], match_score=_match_score_for_rank(index))
        for index, job_id in enumerate(ranked_ids)
    ]

    return JobMatchEnvelope(
        **build_response_metadata(request),
        data=JobMatchData(
            skills=payload.skills,
            experience_years=payload.experience_years,
            preferred_location=payload.preferred_location,
            remote_preferred=payload.remote_preferred,
            count=len(matches),
            matches=matches,
        ),
        error=None,
    )


@router.post(
    "/skills-gap",
    response_model=SkillsGapEnvelope,
    summary="Estimate missing skills for a target role",
    description=(
        "Ask Gemini to compare the user's current skills with a target job title and "
        "return a structured missing-skills summary."
    ),
    response_description="Standard success envelope containing a structured skills-gap analysis.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {"description": "Skills-gap analysis returned successfully.", "content": {"application/json": {"example": SKILLS_GAP_SUCCESS_EXAMPLE}}},
        422: error_response_doc("Request validation failed.", VALIDATION_ERROR_EXAMPLE),
        429: error_response_doc("AI endpoint rate limit exceeded.", RATE_LIMIT_EXAMPLE),
        502: error_response_doc("Gemini request failed or returned invalid JSON.", AI_RESPONSE_ERROR_EXAMPLE),
        503: error_response_doc("Gemini is not configured.", AI_CONFIGURATION_ERROR_EXAMPLE),
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def skills_gap(
    request: Request,
    payload: SkillsGapRequest = Body(
        openapi_examples={"default": {"summary": "Skills gap input", "value": SKILLS_GAP_REQUEST_EXAMPLE}}
    ),
) -> SkillsGapEnvelope:
    gemini_client = request.app.state.gemini_client
    ai_rate_limiter = request.app.state.ai_rate_limiter
    api_key = getattr(request.state, "api_key", None)

    if api_key:
        ai_rate_limiter.enforce(api_key)

    analysis_payload = gemini_client.analyze_skills_gap(
        current_skills=payload.current_skills,
        target_job_title=payload.target_job_title,
    )
    try:
        analysis = SkillsGapResult.model_validate(analysis_payload)
    except ValidationError as exc:
        raise AIResponseError("Gemini returned JSON in an unexpected shape.", details=[str(exc)]) from exc

    return SkillsGapEnvelope(
        **build_response_metadata(request),
        data=SkillsGapData(
            current_skills=payload.current_skills,
            target_job_title=payload.target_job_title,
            analysis=analysis,
        ),
        error=None,
    )
