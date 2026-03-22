import pytest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


VALID_API_KEY = "test-api-key"
INVALID_API_KEY = "wrong-key"


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _auth_headers(api_key: str = VALID_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def test_health_endpoint_returns_expected_shape():
    settings = Settings(sqlite_db_path=_memory_db_uri("health"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == settings.app_name
    assert payload["data"]["version"] == settings.app_version
    assert payload["data"]["database"] == "ok"
    assert payload["error"] is None
    assert "request_id" in payload
    assert "timestamp" in payload


def test_health_endpoint_requires_api_key():
    settings = Settings(sqlite_db_path=_memory_db_uri("health-auth"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        missing_response = client.get("/health")
        invalid_response = client.get("/health", headers=_auth_headers(INVALID_API_KEY))

    assert missing_response.status_code == 401
    assert missing_response.json()["data"] is None
    assert missing_response.json()["error"]["code"] == "authentication_required"
    assert invalid_response.status_code == 403
    assert invalid_response.json()["data"] is None
    assert invalid_response.json()["error"]["code"] == "authentication_invalid"


def test_health_probe_is_public_and_returns_ready_status():
    settings = Settings(sqlite_db_path=_memory_db_uri("health-probe"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_probe_returns_503_when_repository_is_unhealthy():
    settings = Settings(sqlite_db_path=_memory_db_uri("health-probe-fail"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        app.state.repository.health_check = lambda: False
        response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json() == {"status": "error"}


def test_app_startup_fails_fast_when_api_keys_are_missing():
    settings = Settings(sqlite_db_path=_memory_db_uri("health-startup"), api_keys=())
    app = create_app(settings)

    with pytest.raises(RuntimeError, match="API_KEYS"):
        with TestClient(app):
            pass


def test_openapi_schema_includes_api_key_security_and_examples():
    settings = Settings(sqlite_db_path=_memory_db_uri("health-openapi"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert "APIKeyHeader" in payload["components"]["securitySchemes"]
    health_get = payload["paths"]["/health"]["get"]
    assert health_get["security"] == [{"APIKeyHeader": []}]
    assert "example" in health_get["responses"]["200"]["content"]["application/json"]
    assert "/healthz" not in payload["paths"]
