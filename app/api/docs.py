from __future__ import annotations

from app.models.schemas import ErrorEnvelope


AUTH_REQUIRED_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f00",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "authentication_required",
        "message": "A valid X-API-Key header is required.",
        "details": ["Required header: X-API-Key"],
    },
}

AUTH_INVALID_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f01",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "authentication_invalid",
        "message": "The provided API key is invalid.",
        "details": ["The provided X-API-Key value is not recognized."],
    },
}

VALIDATION_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f02",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "validation_error",
        "message": "The request parameters did not pass validation.",
        "details": ["query.page: Input should be greater than or equal to 1"],
    },
}

NOT_FOUND_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f03",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "not_found",
        "message": "The requested resource was not found.",
        "details": None,
    },
}

UPSTREAM_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f04",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "upstream_source_error",
        "message": "Failed to fetch public job listings from the configured sources.",
        "details": None,
    },
}

INTERNAL_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f05",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "internal_server_error",
        "message": "An unexpected error occurred.",
        "details": None,
    },
}


def error_response_doc(description: str, example: dict[str, object]) -> dict[str, object]:
    """Build a reusable OpenAPI response entry for error envelopes."""
    return {
        "model": ErrorEnvelope,
        "description": description,
        "content": {
            "application/json": {
                "example": example,
            }
        },
    }


AUTH_ERROR_RESPONSES = {
    401: error_response_doc("Missing API key.", AUTH_REQUIRED_EXAMPLE),
    403: error_response_doc("Invalid API key.", AUTH_INVALID_EXAMPLE),
}
