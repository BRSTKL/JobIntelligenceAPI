from __future__ import annotations

from fastapi import APIRouter, Request, Security
from fastapi.responses import JSONResponse

from app.api.docs import AUTH_ERROR_RESPONSES, INTERNAL_ERROR_EXAMPLE, error_response_doc
from app.core.auth import require_api_key
from app.core.responses import build_response_metadata
from app.models.schemas import HealthData, HealthEnvelope


HEALTH_SUCCESS_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f5000",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": {
        "status": "ok",
        "service": "Job Intelligence API",
        "version": "0.1.0",
        "database": "ok",
    },
    "error": None,
}

router = APIRouter(prefix="/health", tags=["Health"])
probe_router = APIRouter()


@router.get(
    "",
    response_model=HealthEnvelope,
    dependencies=[Security(require_api_key)],
    summary="Check API and database health",
    description=(
        "Return the current authenticated service health status and a lightweight SQLite "
        "connectivity check for product integrations."
    ),
    response_description="Standard success envelope containing health information.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Health status returned successfully.",
            "content": {
                "application/json": {
                    "example": HEALTH_SUCCESS_EXAMPLE,
                }
            },
        },
        500: error_response_doc("Unexpected server error.", INTERNAL_ERROR_EXAMPLE),
    },
)
def get_health(request: Request) -> HealthEnvelope:
    repository = request.app.state.repository
    settings = request.app.state.settings

    return HealthEnvelope(
        **build_response_metadata(request),
        data=HealthData(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            database="ok" if repository.health_check() else "error",
        ),
        error=None,
    )


@probe_router.get("/healthz", include_in_schema=False)
def get_health_probe(request: Request) -> JSONResponse:
    """Return a tiny readiness payload for deployment platform health checks."""
    repository = request.app.state.repository
    if repository.health_check():
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "error"})
