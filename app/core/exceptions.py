from __future__ import annotations


class ApiError(Exception):
    """Base exception for predictable API errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(ApiError):
    """Raised when an expected resource does not exist."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(404, "not_found", message, details)


class AuthenticationRequiredError(ApiError):
    """Raised when the API key header is missing."""

    def __init__(self) -> None:
        super().__init__(
            401,
            "authentication_required",
            "A valid X-API-Key header is required.",
            ["Required header: X-API-Key"],
        )


class AuthenticationInvalidError(ApiError):
    """Raised when the provided API key is not recognized."""

    def __init__(self) -> None:
        super().__init__(
            403,
            "authentication_invalid",
            "The provided API key is invalid.",
            ["The provided X-API-Key value is not recognized."],
        )


class UpstreamSourceError(ApiError):
    """Raised when the public job source cannot be reached or parsed upstream."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(502, "upstream_source_error", message, details)


class RateLimitExceededError(ApiError):
    """Raised when a client exceeds a configured request limit."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(429, "rate_limit_exceeded", message, details)


class AIConfigurationError(ApiError):
    """Raised when AI features are requested without the required config."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(503, "ai_configuration_error", message, details)


class AIProviderError(ApiError):
    """Raised when the AI provider request fails."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(502, "ai_provider_error", message, details)


class AIResponseError(ApiError):
    """Raised when the AI provider returns invalid data."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(502, "ai_response_error", message, details)
