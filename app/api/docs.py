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

RATE_LIMIT_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f06",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "rate_limit_exceeded",
        "message": "AI endpoint rate limit exceeded.",
        "details": ["Limit: 2 requests per 60 seconds."],
    },
}

AI_CONFIGURATION_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f07",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "ai_configuration_error",
        "message": "GEMINI_API_KEY is not configured.",
        "details": ["Set GEMINI_API_KEY to enable AI endpoints."],
    },
}

AI_PROVIDER_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f08",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "ai_provider_error",
        "message": "Gemini request failed.",
        "details": ["provider failure"],
    },
}

AI_RESPONSE_ERROR_EXAMPLE = {
    "request_id": "9c37cf00-4b3d-4dd0-8ef0-b0f8f44f4f09",
    "timestamp": "2026-03-22T09:00:00Z",
    "data": None,
    "error": {
        "code": "ai_response_error",
        "message": "Gemini returned invalid JSON.",
        "details": ["Expecting value: line 1 column 1 (char 0)"],
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
