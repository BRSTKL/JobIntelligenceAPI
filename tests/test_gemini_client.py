from datetime import UTC, datetime

import pytest

from app.core.exceptions import AIConfigurationError, AIResponseError
from app.models.schemas import JobRecord
from app.services.gemini_client import GeminiClientService


class FakeGeminiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeGeminiModels:
    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def generate_content(self, *, model: str, contents: str):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeGeminiClient:
    def __init__(self, outcome) -> None:
        self.models = FakeGeminiModels(outcome)


def _job(job_id: str) -> JobRecord:
    return JobRecord(
        id=job_id,
        source="arbeitnow",
        source_job_id=job_id,
        source_job_url=f"https://example.com/jobs/{job_id}",
        language="en",
        title="Python Engineer",
        normalized_title="Python Engineer",
        company="Acme",
        location_raw="Remote",
        location_city=None,
        location_country=None,
        remote_type="remote",
        employment_type="full_time",
        seniority_level="mid",
        salary_text=None,
        description_snippet="Build APIs.",
        skills=["python", "fastapi"],
        posted_at=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
        freshness_days=0,
    )


def test_gemini_client_parses_match_job_ids():
    service = GeminiClientService(api_key="gemini-test-key")
    service._client = FakeGeminiClient(FakeGeminiResponse('["job-1", "job-2"]'))

    job_ids = service.match_jobs(
        skills=["python"],
        experience_years=3,
        preferred_location="Istanbul",
        remote_preferred=True,
        jobs=[_job("job-1"), _job("job-2")],
    )

    assert job_ids == ["job-1", "job-2"]


def test_gemini_client_strips_code_fences_for_skills_gap():
    service = GeminiClientService(api_key="gemini-test-key")
    service._client = FakeGeminiClient(
        FakeGeminiResponse(
            """```json
            {
              "missing_skills": ["kubernetes"],
              "learning_priority": "high",
              "estimated_learning_time": "3-6 months",
              "recommended_resources": ["resource1"]
            }
            ```"""
        )
    )

    payload = service.analyze_skills_gap(
        current_skills=["python", "django"],
        target_job_title="Senior DevOps Engineer",
    )

    assert payload["missing_skills"] == ["kubernetes"]
    assert payload["learning_priority"] == "high"


def test_gemini_client_requires_api_key():
    service = GeminiClientService(api_key=None)

    with pytest.raises(AIConfigurationError):
        service.analyze_skills_gap(current_skills=["python"], target_job_title="DevOps Engineer")


def test_gemini_client_raises_on_invalid_json():
    service = GeminiClientService(api_key="gemini-test-key")
    service._client = FakeGeminiClient(FakeGeminiResponse("not-json"))

    with pytest.raises(AIResponseError):
        service.match_jobs(
            skills=["python"],
            experience_years=3,
            preferred_location=None,
            remote_preferred=True,
            jobs=[_job("job-1")],
        )
