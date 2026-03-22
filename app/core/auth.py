from __future__ import annotations

from typing import Annotated

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from app.core.exceptions import AuthenticationInvalidError, AuthenticationRequiredError


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key required to access Job Intelligence API endpoints.",
)


def require_api_key(
    request: Request,
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> str:
    """Validate the incoming X-API-Key header against configured keys."""
    if api_key is None:
        raise AuthenticationRequiredError()

    valid_api_keys = request.app.state.valid_api_keys
    if api_key not in valid_api_keys:
        raise AuthenticationInvalidError()

    request.state.api_key = api_key
    return api_key
