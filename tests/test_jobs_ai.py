from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AIProviderError, AIResponseError
from app.main import create_app
from app.models.schemas import JobRecord
from app.services.ai_rate_limiter import AIRateLimiter


VALID_API_KEY = "test-api-key"
INVALID_API_KEY = "wrong-key"


class FakeGeminiService:
    def __init__(self) -> None:
        self.match_ids = ["job-1", "job-2", "job-2", "missing-id"]
        self.skills_gap_payload = {
            "missing_skills": ["kubernetes", "terraform"],
            "learning_priority": "high",
            "estimated_learning_time": "3-6 months",
            "recommended_resources": ["resource1", "resource2"],
        }

    def match_jobs(self, **kwargs):
        return list(self.match_ids)

    def analyze_skills_gap(self, **kwargs):
        return dict(self.skills_gap_payload)


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _auth_headers(api_key: str = VALID_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def _job(job_id: str, title: str = "Python Engineer") -> JobRecord:
    return JobRecord(
        id=job_id,
        source="arbeitnow",
        source_job_id=job_id,
        source_job_url=f"https://example.com/jobs/{job_id}",
        language="en",
        title=title,
        normalized_title=title,
        company="Acme",
        location_raw="Istanbul, Turkey",
        location_city="Istanbul",
        location_country="Turkey",
        remote_type="remote",
        employment_type="full_time",
        seniority_level="mid",
        salary_text=None,
        description_snippet="Build APIs with Python.",
        skills=["python", "fastapi", "docker"],
        posted_at=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        freshness_days=0,
    )


def _build_test_app(*, gemini_api_key: str | None = "gemini-test-key"):
    settings = Settings(
        sqlite_db_path=_memory_db_uri("jobs-ai"),
        api_keys=(VALID_API_KEY,),
        gemini_api_key=gemini_api_key,
    )
    app = create_app(settings)
    app.state.repository.initialize()
    app.state.repository.upsert_jobs([_job("job-1"), _job("job-2", title="Platform Engineer")])
    if gemini_api_key:
        app.state.gemini_client = FakeGeminiService()
    app.state.ai_rate_limiter = AIRateLimiter(limit=2, window_seconds=60, time_provider=lambda: 1_000.0)
    return app


def test_jobs_match_returns_ranked_matches():
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/jobs/match",
            headers=_auth_headers(),
            json={
                "skills": ["python", "fastapi", "docker"],
                "experience_years": 3,
                "preferred_location": "Istanbul",
                "remote_preferred": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] is None
    assert payload["data"]["count"] == 2
    assert [match["job"]["id"] for match in payload["data"]["matches"]] == ["job-1", "job-2"]
    assert [match["match_score"] for match in payload["data"]["matches"]] == [100, 90]


def test_jobs_skills_gap_returns_structured_analysis():
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/jobs/skills-gap",
            headers=_auth_headers(),
            json={
                "current_skills": ["python", "django"],
                "target_job_title": "Senior DevOps Engineer",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] is None
    assert payload["data"]["analysis"]["missing_skills"] == ["kubernetes", "terraform"]
    assert payload["data"]["analysis"]["learning_priority"] == "high"


def test_ai_endpoints_require_valid_api_key():
    app = _build_test_app()

    with TestClient(app) as client:
        missing_response = client.post("/jobs/match", json={"skills": ["python"], "experience_years": 1})
        invalid_response = client.post(
            "/jobs/skills-gap",
            headers=_auth_headers(INVALID_API_KEY),
            json={"current_skills": ["python"], "target_job_title": "DevOps Engineer"},
        )

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 403


def test_ai_endpoints_return_503_when_gemini_key_is_missing():
    app = _build_test_app(gemini_api_key=None)

    with TestClient(app) as client:
        response = client.post(
            "/jobs/match",
            headers=_auth_headers(),
            json={"skills": ["python"], "experience_years": 2},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_configuration_error"


def test_ai_endpoints_rate_limit_per_api_key():
    app = _build_test_app()

    with TestClient(app) as client:
        for _ in range(2):
            response = client.post(
                "/jobs/match",
                headers=_auth_headers(),
                json={"skills": ["python"], "experience_years": 2},
            )
            assert response.status_code == 200

        third_response = client.post(
            "/jobs/skills-gap",
            headers=_auth_headers(),
            json={"current_skills": ["python"], "target_job_title": "DevOps Engineer"},
        )

    assert third_response.status_code == 429
    assert third_response.json()["error"]["code"] == "rate_limit_exceeded"


def test_ai_endpoints_return_502_for_provider_and_response_errors():
    app = _build_test_app()

    def failing_match_jobs(**kwargs):
        raise AIProviderError("Gemini request failed.", details=["provider failure"])

    def failing_skills_gap(**kwargs):
        raise AIResponseError("Gemini returned invalid JSON.", details=["bad json"])

    app.state.gemini_client.match_jobs = failing_match_jobs
    app.state.gemini_client.analyze_skills_gap = failing_skills_gap

    with TestClient(app) as client:
        match_response = client.post(
            "/jobs/match",
            headers=_auth_headers(),
            json={"skills": ["python"], "experience_years": 2},
        )
        gap_response = client.post(
            "/jobs/skills-gap",
            headers=_auth_headers(),
            json={"current_skills": ["python"], "target_job_title": "DevOps Engineer"},
        )

    assert match_response.status_code == 502
    assert match_response.json()["error"]["code"] == "ai_provider_error"
    assert gap_response.status_code == 502
    assert gap_response.json()["error"]["code"] == "ai_response_error"


def test_ai_endpoints_return_validation_errors_for_bad_payloads():
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/jobs/skills-gap",
            headers=_auth_headers(),
            json={"current_skills": [], "target_job_title": ""},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
