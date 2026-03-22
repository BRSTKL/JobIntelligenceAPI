from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.schemas import EmploymentTypeEnum, JobRecord, RemoteTypeEnum, SeniorityLevelEnum


VALID_API_KEY = "test-api-key"


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": VALID_API_KEY}


def _job(job_id: str, company: str, location: str, skills: list[str]) -> JobRecord:
    return JobRecord(
        id=job_id,
        source="remoteok",
        source_job_id=job_id,
        source_job_url=f"https://example.com/jobs/{job_id}",
        title=f"{company} Engineer",
        normalized_title="Engineer",
        company=company,
        location_raw=location,
        location_city=location.split(",")[0],
        location_country=location.split(",")[-1].strip() if "," in location else None,
        remote_type=RemoteTypeEnum.remote,
        employment_type=EmploymentTypeEnum.full_time,
        seniority_level=SeniorityLevelEnum.mid,
        salary_text=None,
        description_snippet="Example job description",
        skills=skills,
        posted_at=datetime.now(tz=UTC),
        freshness_days=0,
    )


def test_insight_endpoints_return_top_items():
    settings = Settings(sqlite_db_path=_memory_db_uri("insights"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        app.state.repository.upsert_jobs(
            [
                _job("1", "Acme", "Berlin, Germany", ["python", "fastapi"]),
                _job("2", "Acme", "Berlin, Germany", ["python", "docker"]),
                _job("3", "Orbit Labs", "London, United Kingdom", ["typescript", "react"]),
            ]
        )

        skills_response = client.get("/insights/skills", headers=_auth_headers())
        companies_response = client.get("/insights/companies", headers=_auth_headers())
        locations_response = client.get("/insights/locations", headers=_auth_headers())

    assert skills_response.status_code == 200
    assert skills_response.json()["error"] is None
    assert skills_response.json()["data"]["items"][0] == {"name": "python", "count": 2}
    assert companies_response.status_code == 200
    assert companies_response.json()["data"]["items"][0] == {"name": "Acme", "count": 2}
    assert locations_response.status_code == 200
    assert locations_response.json()["data"]["items"][0] == {"name": "Berlin, Germany", "count": 2}


def test_insight_endpoints_return_empty_lists_when_no_jobs_exist():
    settings = Settings(sqlite_db_path=_memory_db_uri("empty-insights"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/insights/skills", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["count"] == 0
    assert payload["data"]["items"] == []
