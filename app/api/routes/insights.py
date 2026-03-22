from __future__ import annotations

from fastapi import APIRouter, Query, Request, Security

from app.api.docs import AUTH_ERROR_RESPONSES, INTERNAL_ERROR_EXAMPLE, error_response_doc
from app.core.auth import require_api_key
from app.core.responses import build_response_metadata
from app.models.schemas import InsightsData, InsightsEnvelope


INSIGHTS_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5200",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "dimension": "skills",
        "count": 2,
        "items": [
            {"name": "python", "count": 2},
            {"name": "fastapi", "count": 1},
        ],
    },
    "error": None,
}

router = APIRouter(prefix="/insights", tags=["Insights"], dependencies=[Security(require_api_key)])


def _build_response(request: Request, dimension: str, items) -> InsightsEnvelope:
    return InsightsEnvelope(
        **build_response_metadata(request),
        data=InsightsData(
            dimension=dimension,
            count=len(items),
            items=items,
        ),
        error=None,
    )


@router.get(
    "/skills",
    response_model=InsightsEnvelope,
    summary="Get top extracted skills",
    description=(
        "Return the most common normalized skills across stored jobs so you can quickly see "
        "which capabilities appear most often in the current dataset."
    ),
    response_description="Standard success envelope containing top skill insights.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Skill insights returned successfully.",
            "content": {
                "application/json": {
                    "example": INSIGHTS_SUCCESS_EXAMPLE,
                }
            },
        },
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def get_skills_insights(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of skill rows to return."),
) -> InsightsEnvelope:
    repository = request.app.state.repository
    intelligence = request.app.state.intelligence
    items = intelligence.top_skills(repository.list_jobs(), limit=limit)
    return _build_response(request, "skills", items)


@router.get(
    "/companies",
    response_model=InsightsEnvelope,
    summary="Get top companies",
    description=(
        "Return the most common companies across stored jobs for simple hiring activity "
        "tracking and company-level dashboards."
    ),
    response_description="Standard success envelope containing top company insights.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Company insights returned successfully.",
            "content": {
                "application/json": {
                    "example": {
                        **INSIGHTS_SUCCESS_EXAMPLE,
                        "data": {
                            "dimension": "companies",
                            "count": 2,
                            "items": [
                                {"name": "Acme", "count": 2},
                                {"name": "Orbit Labs", "count": 1},
                            ],
                        },
                    },
                }
            },
        },
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def get_company_insights(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of company rows to return."),
) -> InsightsEnvelope:
    repository = request.app.state.repository
    intelligence = request.app.state.intelligence
    items = intelligence.top_companies(repository.list_jobs(), limit=limit)
    return _build_response(request, "companies", items)


@router.get(
    "/locations",
    response_model=InsightsEnvelope,
    summary="Get top locations",
    description=(
        "Return the most common locations across stored jobs to support basic geography and "
        "market trend reporting."
    ),
    response_description="Standard success envelope containing top location insights.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Location insights returned successfully.",
            "content": {
                "application/json": {
                    "example": {
                        **INSIGHTS_SUCCESS_EXAMPLE,
                        "data": {
                            "dimension": "locations",
                            "count": 2,
                            "items": [
                                {"name": "Berlin, Germany", "count": 2},
                                {"name": "London, United Kingdom", "count": 1},
                            ],
                        },
                    },
                }
            },
        },
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def get_location_insights(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of location rows to return."),
) -> InsightsEnvelope:
    repository = request.app.state.repository
    intelligence = request.app.state.intelligence
    items = intelligence.top_locations(repository.list_jobs(), limit=limit)
    return _build_response(request, "locations", items)
