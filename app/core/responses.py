from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.schemas import ErrorEnvelope, ErrorInfo


def build_response_metadata(request: Request) -> dict[str, object]:
    """Return the standard metadata attached to every API response."""
    return {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "timestamp": datetime.now(tz=UTC),
    }


def build_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[str] | None = None,
) -> JSONResponse:
    """Return the standard JSON error envelope."""
    payload = ErrorEnvelope(
        **build_response_metadata(request),
        data=None,
        error=ErrorInfo(code=code, message=message, details=details),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
