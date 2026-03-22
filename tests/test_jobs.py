import httpx
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.multi_source_fetcher import SourcePayload


VALID_API_KEY = "test-api-key"
INVALID_API_KEY = "wrong-key"

ARBEITNOW_PAYLOAD = """
{
  "jobs": [
    {
      "id": "1001",
      "title": "Senior Python Backend Engineer",
      "company_name": "Acme",
      "location": "Berlin, Germany",
      "remote": true,
      "job_type": "full_time",
      "tags": ["Python", "FastAPI", "Docker"],
      "url": "https://example.com/jobs/1001",
      "created_at": "2026-03-20T10:00:00+00:00",
      "description": "Build FastAPI services with Python, Docker, and AWS."
    }
  ]
}
"""

REMOTIVE_PAYLOAD = """
{
  "jobs": [
    {
      "id": "2001",
      "title": "Junior Data Analyst",
      "company_name": "Beta Analytics",
      "candidate_required_location": "London, United Kingdom",
      "job_type": "contract",
      "tags": ["SQL", "Python"],
      "url": "https://example.com/jobs/2001",
      "publication_date": "2026-03-18T08:00:00+00:00",
      "description": "Work with SQL, dashboards, and Python reporting."
    }
  ]
}
"""

THEMUSE_PAYLOAD = """
{
  "results": [
    {
      "id": 3001,
      "name": "Staff Frontend Engineer",
      "company": { "name": "Orbit Labs" },
      "locations": [{ "name": "Remote" }],
      "refs": { "landing_page": "https://example.com/jobs/3001" },
      "publication_date": "2026-03-10T09:00:00+00:00"
    }
  ]
}
"""


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _auth_headers(api_key: str = VALID_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def _sample_source_payloads() -> list[SourcePayload]:
    return [
        SourcePayload(source="arbeitnow", url="https://www.arbeitnow.com/api/job-board-api", body=ARBEITNOW_PAYLOAD),
        SourcePayload(source="remotive", url="https://remotive.com/api/remote-jobs", body=REMOTIVE_PAYLOAD),
        SourcePayload(source="themuse", url="https://www.themuse.com/api/public/jobs?page=1", body=THEMUSE_PAYLOAD),
    ]


def _build_test_app(monkeypatch, payloads: list[SourcePayload] | None = None):
    settings = Settings(sqlite_db_path=_memory_db_uri("jobs"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    async def fake_fetch_source_payloads(query=None):
        return payloads or _sample_source_payloads()

    monkeypatch.setattr(app.state.fetcher, "fetch_source_payloads", fake_fetch_source_payloads)
    return app


def test_jobs_search_returns_normalized_jobs(monkeypatch):
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.get(
            "/jobs/search",
            headers=_auth_headers(),
            params={
                "q": "python",
                "employment_type": "full_time",
                "seniority": "senior",
                "remote": "true",
                "limit": 10,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] is None
    assert payload["data"]["query"] == "python"
    assert payload["data"]["filters"]["employment_type"] == "full_time"
    assert payload["data"]["count"] == 1
    assert payload["data"]["pagination"]["total_results"] == 1
    assert payload["data"]["jobs"][0]["company"] == "Acme"
    assert payload["data"]["jobs"][0]["source"] == "arbeitnow"
    assert payload["data"]["jobs"][0]["normalized_title"] == "Python Backend Engineer"
    assert payload["data"]["jobs"][0]["remote_type"] == "remote"
    assert payload["data"]["jobs"][0]["skills"] == ["aws", "docker", "fastapi", "python"]


def test_jobs_search_supports_pagination_and_job_detail(monkeypatch):
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        page_response = client.get("/jobs/search", headers=_auth_headers(), params={"page": 2, "limit": 1})
        assert page_response.status_code == 200
        page_payload = page_response.json()
        assert page_payload["data"]["count"] == 1
        assert page_payload["data"]["pagination"]["page"] == 2
        assert page_payload["data"]["pagination"]["total_pages"] == 3

        job_id = page_payload["data"]["jobs"][0]["id"]
        detail_response = client.get(f"/jobs/{job_id}", headers=_auth_headers())

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["error"] is None
    assert detail_payload["data"]["job"]["id"] == job_id
    assert detail_payload["data"]["job"]["source"] == "remotive"


def test_jobs_search_validates_inputs_and_handles_missing_job(monkeypatch):
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        invalid_response = client.get("/jobs/search", headers=_auth_headers(), params={"page": 0})
        missing_response = client.get("/jobs/does-not-exist", headers=_auth_headers())

    assert invalid_response.status_code == 422
    assert invalid_response.json()["data"] is None
    assert invalid_response.json()["error"]["code"] == "validation_error"
    assert invalid_response.json()["error"]["details"]
    assert missing_response.status_code == 404
    assert missing_response.json()["data"] is None
    assert missing_response.json()["error"]["code"] == "not_found"


def test_jobs_search_handles_partial_records_without_crashing(monkeypatch):
    partial_payloads = [
        SourcePayload(
            source="arbeitnow",
            url="https://www.arbeitnow.com/api/job-board-api",
            body="""
            {
              "jobs": [
                {
                  "id": "partial-1",
                  "company_name": "Partial Co"
                }
              ]
            }
            """,
        ),
        SourcePayload(
            source="themuse",
            url="https://www.themuse.com/api/public/jobs?page=1",
            body="""
            {
              "results": [
                {
                  "id": 3002,
                  "name": "Platform Engineer",
                  "company": { "name": "Attr Co" },
                  "refs": { "landing_page": null },
                  "publication_date": "not-a-date"
                }
              ]
            }
            """,
        ),
    ]
    app = _build_test_app(monkeypatch, payloads=partial_payloads)

    with TestClient(app) as client:
        response = client.get("/jobs/search", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] is None
    assert payload["data"]["count"] == 2

    partial_company_job = next(job for job in payload["data"]["jobs"] if job["source_job_id"] == "partial-1")
    assert partial_company_job["company"] == "Partial Co"
    assert partial_company_job["source_job_url"] is None
    assert partial_company_job["remote_type"] is None
    assert partial_company_job["employment_type"] is None
    assert partial_company_job["seniority_level"] is None
    assert partial_company_job["freshness_days"] is None

    partial_attr_job = next(job for job in payload["data"]["jobs"] if job["source_job_id"] == "3002")
    assert partial_attr_job["title"] == "Platform Engineer"
    assert partial_attr_job["skills"] == []
    assert partial_attr_job["freshness_days"] is None


def test_jobs_endpoints_reject_missing_and_invalid_api_keys(monkeypatch):
    app = _build_test_app(monkeypatch)

    with TestClient(app) as client:
        missing_response = client.get("/jobs/search")
        invalid_response = client.get("/jobs/search", headers=_auth_headers(INVALID_API_KEY))

    assert missing_response.status_code == 401
    assert missing_response.json()["data"] is None
    assert missing_response.json()["error"]["code"] == "authentication_required"
    assert invalid_response.status_code == 403
    assert invalid_response.json()["data"] is None
    assert invalid_response.json()["error"]["code"] == "authentication_invalid"


def test_jobs_search_returns_upstream_error_envelope(monkeypatch):
    settings = Settings(sqlite_db_path=_memory_db_uri("jobs-upstream"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    async def failing_fetch_source_payloads(query=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(app.state.fetcher, "fetch_source_payloads", failing_fetch_source_payloads)

    with TestClient(app) as client:
        response = client.get("/jobs/search", headers=_auth_headers())

    assert response.status_code == 502
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "upstream_source_error"


def test_jobs_search_deduplicates_same_url_across_sources(monkeypatch):
    duplicate_payloads = [
        SourcePayload(source="arbeitnow", url="https://www.arbeitnow.com/api/job-board-api", body=ARBEITNOW_PAYLOAD),
        SourcePayload(
            source="remotive",
            url="https://remotive.com/api/remote-jobs",
            body="""
            {
              "jobs": [
                {
                  "id": "dup-1",
                  "title": "Senior Python Backend Engineer",
                  "company_name": "Acme Mirror",
                  "candidate_required_location": "Germany",
                  "job_type": "full_time",
                  "tags": ["Python"],
                  "url": "https://example.com/jobs/1001",
                  "publication_date": "2026-03-20T10:00:00+00:00"
                }
              ]
            }
            """,
        ),
    ]
    app = _build_test_app(monkeypatch, payloads=duplicate_payloads)

    with TestClient(app) as client:
        response = client.get("/jobs/search", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["count"] == 1
    assert payload["data"]["jobs"][0]["source"] == "arbeitnow"
