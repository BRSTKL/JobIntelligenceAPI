from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.api.routes.health import probe_router, router as health_router
from app.api.routes.insights import router as insights_router
from app.api.routes.jobs import router as jobs_router
from app.core.config import (
    Settings,
    SettingsValidationError,
    get_bootstrap_log_level,
    get_settings,
    load_env_file,
)
from app.core.exceptions import ApiError
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.core.responses import build_error_response
from app.services.cache import MemoryCache
from app.services.intelligence import IntelligenceService
from app.services.multi_source_fetcher import MultiSourceJobFetcher
from app.services.normalizer import JobNormalizer
from app.services.parser import PublicJobParser
from app.services.repository import SQLiteRepository


logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {
        "name": "Jobs",
        "description": (
            "Search structured public job records and retrieve individual job details for "
            "job boards, matching flows, and career products."
        ),
    },
    {
        "name": "Insights",
        "description": (
            "Turn stored job listings into quick market signals such as top skills, "
            "companies, and locations."
        ),
    },
    {
        "name": "Health",
        "description": "Authenticated service health checks for product integrations.",
    },
]


def _flatten_validation_errors(exc: RequestValidationError) -> list[str]:
    """Convert FastAPI validation errors into a simple list of readable strings."""
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []))
        message = error.get("msg", "Invalid request parameter.")
        details.append(f"{location}: {message}" if location else message)
    return details


def _http_exception_error_code(status_code: int) -> str:
    """Map framework HTTP status codes to the public error code format."""
    if status_code == 404:
        return "not_found"
    return f"http_{status_code}"


def _log_startup_summary(settings: Settings, api_key_count: int) -> None:
    """Log one concise startup summary for local and cloud deployments."""
    logger.info(
        (
            "Application startup complete | service=%s version=%s host=0.0.0.0 port=%s "
            "sqlite_db_path=%s sources=arbeitnow=%s,remotive=%s,themuse=%s,kariyer=%s "
            "cache_ttl_seconds=%s default_page_size=%s max_page_size=%s "
            "api_key_count=%s health_probe=/healthz"
        ),
        settings.app_name,
        settings.app_version,
        settings.port,
        settings.sqlite_db_path,
        settings.arbeitnow_source_url,
        settings.remotive_source_url,
        settings.themuse_source_url,
        settings.kariyer_source_url,
        settings.cache_ttl_seconds,
        settings.default_page_size,
        settings.max_page_size,
        api_key_count,
    )


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    settings.validate()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not app.state.valid_api_keys:
            message = (
                "Startup validation failed: API_KEYS must contain at least one comma-separated "
                "API key before the API can start."
            )
            logger.error(message)
            raise RuntimeError(message)
        app.state.repository.initialize()
        if not app.state.repository.health_check():
            message = "Startup validation failed: SQLite health check failed after repository initialization."
            logger.error(message)
            raise RuntimeError(message)
        _log_startup_summary(app.state.settings, len(app.state.valid_api_keys))
        yield

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.valid_api_keys = set(settings.api_keys)
    app.state.cache = MemoryCache(settings.cache_ttl_seconds)
    app.state.fetcher = MultiSourceJobFetcher(settings)
    app.state.parser = PublicJobParser()
    app.state.normalizer = JobNormalizer()
    app.state.intelligence = IntelligenceService()
    app.state.repository = SQLiteRepository(settings.sqlite_db_path)

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return build_error_response(
            request=request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error: %s", exc.errors())
        return build_error_response(
            request=request,
            status_code=422,
            code="validation_error",
            message="The request parameters did not pass validation.",
            details=_flatten_validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        if exc.status_code == 404 and exc.detail == "Not Found":
            message = "The requested resource was not found."
        return build_error_response(
            request=request,
            status_code=exc.status_code,
            code=_http_exception_error_code(exc.status_code),
            message=message,
            details=None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error")
        return build_error_response(
            request=request,
            status_code=500,
            code="internal_server_error",
            message="An unexpected error occurred.",
            details=None,
        )

    app.include_router(health_router)
    app.include_router(probe_router)
    app.include_router(jobs_router)
    app.include_router(insights_router)

    return app


def build_application() -> FastAPI:
    """Build the FastAPI application with bootstrap logging for config failures."""
    configure_logging(get_bootstrap_log_level())
    try:
        load_env_file()
        configure_logging(get_bootstrap_log_level())
        return create_app()
    except SettingsValidationError as exc:
        logger.error("Application configuration is invalid.\n%s", exc)
        raise


app = build_application()


def run() -> None:
    """Run the API using the validated PORT setting from the environment."""
    settings = app.state.settings
    logger.info("Launching ASGI server on http://0.0.0.0:%s", settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    run()
