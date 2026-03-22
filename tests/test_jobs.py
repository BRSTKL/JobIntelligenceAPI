import httpx
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


VALID_API_KEY = "test-api-key"
INVALID_API_KEY = "wrong-key"

SAMPLE_HTML = """
<html>
  <body>
    <table>
      <tr class="job" data-id="1001" data-company="Acme" data-position="Senior Python Backend Engineer" data-location="Berlin, Germany" data-tags="Python,FastAPI,Docker" data-employment="Full-time" data-remote="Remote">
        <td class="company">
          <a itemprop="url" href="/remote-jobs/1001">
            <h2 itemprop="title">Senior Python Backend Engineer</h2>
            <h3 itemprop="name">Acme</h3>
          </a>
          <div class="location">Berlin, Germany</div>
          <div class="salary">$100k - $120k</div>
          <div class="description">Build FastAPI services with Python, Docker, and AWS.</div>
          <div class="tags">
            <h3>Python</h3>
            <h3>FastAPI</h3>
            <h3>Docker</h3>
          </div>
          <time datetime="2026-03-20T10:00:00+00:00"></time>
        </td>
      </tr>
      <tr class="job" data-id="1002" data-company="Beta Analytics" data-position="Junior Data Analyst" data-location="London, United Kingdom" data-tags="SQL,Python" data-employment="Contract" data-remote="Onsite">
        <td class="company">
          <a itemprop="url" href="/remote-jobs/1002">
            <h2 itemprop="title">Junior Data Analyst</h2>
            <h3 itemprop="name">Beta Analytics</h3>
          </a>
          <div class="location">London, United Kingdom</div>
          <div class="description">Work with SQL, dashboards, and Python reporting.</div>
          <div class="tags">
            <h3>SQL</h3>
            <h3>Python</h3>
          </div>
          <time datetime="2026-03-18T08:00:00+00:00"></time>
        </td>
      </tr>
      <tr class="job" data-id="1003" data-company="Orbit Labs" data-position="Staff Frontend Engineer" data-location="Worldwide" data-tags="TypeScript,React" data-employment="Part-time" data-remote="Hybrid">
        <td class="company">
          <a itemprop="url" href="/remote-jobs/1003">
            <h2 itemprop="title">Staff Frontend Engineer</h2>
            <h3 itemprop="name">Orbit Labs</h3>
          </a>
          <div class="location">Worldwide</div>
          <div class="description">Build React and TypeScript user interfaces for a global product.</div>
          <div class="tags">
            <h3>React</h3>
            <h3>TypeScript</h3>
          </div>
          <time datetime="2026-03-10T09:00:00+00:00"></time>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

PARTIAL_HTML = """
<html>
  <body>
    <table>
      <tr class="job" data-id="partial-1">
        <td class="company">
          <a href="javascript:void(0)">
            <h3 itemprop="name">Partial Co</h3>
          </a>
          <div class="description"></div>
        </td>
      </tr>
      <tr class="job" data-job-id="partial-2" data-position="Platform Engineer" data-company="Attr Co" data-location="Berlin, Germany" data-date="not-a-date">
        <td class="company">
          <div class="description">Work with Python and FastAPI.</div>
        </td>
      </tr>
      <tr class="job"></tr>
    </table>
  </body>
</html>
"""


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _auth_headers(api_key: str = VALID_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def _build_test_app(monkeypatch):
    settings = Settings(sqlite_db_path=_memory_db_uri("jobs"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    async def fake_fetch_jobs_page(query=None):
        return SAMPLE_HTML

    monkeypatch.setattr(app.state.fetcher, "fetch_jobs_page", fake_fetch_jobs_page)
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
    assert detail_payload["data"]["job"]["source"] == "remoteok"


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
    settings = Settings(sqlite_db_path=_memory_db_uri("jobs-partial"), api_keys=(VALID_API_KEY,))
    app = create_app(settings)

    async def fake_fetch_jobs_page(query=None):
        return PARTIAL_HTML

    monkeypatch.setattr(app.state.fetcher, "fetch_jobs_page", fake_fetch_jobs_page)

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

    partial_attr_job = next(job for job in payload["data"]["jobs"] if job["source_job_id"] == "partial-2")
    assert partial_attr_job["title"] == "Platform Engineer"
    assert partial_attr_job["skills"] == ["fastapi", "python"]
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

    async def failing_fetch_jobs_page(query=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(app.state.fetcher, "fetch_jobs_page", failing_fetch_jobs_page)

    with TestClient(app) as client:
        response = client.get("/jobs/search", headers=_auth_headers())

    assert response.status_code == 502
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "upstream_source_error"
