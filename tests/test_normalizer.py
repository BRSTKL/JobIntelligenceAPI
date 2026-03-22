from datetime import UTC, datetime

from app.models.schemas import EmploymentTypeEnum, RawJobListing, RemoteTypeEnum, SeniorityLevelEnum
from app.services.normalizer import JobNormalizer


FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def _build_normalizer() -> JobNormalizer:
    return JobNormalizer("remoteok", now_provider=lambda: FIXED_NOW)


def test_normalizer_extracts_structured_fields_from_clear_evidence():
    normalizer = _build_normalizer()
    raw_job = RawJobListing(
        source="arbeitnow",
        source_job_id="1001",
        source_job_url="https://example.com/jobs/1001",
        title="Senior API Platform Engineer (Remote, Full-time)",
        company="Acme",
        location_raw="Berlin, Germany",
        tags=["Python", "FastAPI", "Docker"],
        description_text="Build Python, FastAPI, Docker, and AWS services for our platform.",
        posted_at_raw="2026-03-20T10:00:00+00:00",
    )

    job = normalizer.normalize_job(raw_job)

    assert job.source == "arbeitnow"
    assert job.language == "en"
    assert job.normalized_title == "API Platform Engineer"
    assert job.remote_type == RemoteTypeEnum.remote
    assert job.employment_type == EmploymentTypeEnum.full_time
    assert job.seniority_level == SeniorityLevelEnum.senior
    assert job.freshness_days == 2
    assert job.skills == ["aws", "docker", "fastapi", "python"]


def test_normalizer_returns_nulls_for_missing_or_malformed_inference_fields():
    normalizer = _build_normalizer()
    raw_job = RawJobListing(
        source=None,
        source_job_id=None,
        source_job_url="not-a-valid-url",
        title="Platform Engineer",
        company="Partial Co",
        location_raw=None,
        description_text=None,
        posted_at_raw="not-a-date",
    )

    job = normalizer.normalize_job(raw_job)

    assert job.source_job_url is None
    assert job.language == "en"
    assert job.normalized_title == "Platform Engineer"
    assert job.remote_type is None
    assert job.employment_type is None
    assert job.seniority_level is None
    assert job.freshness_days is None
    assert job.skills == []


def test_normalizer_extracts_skills_from_aliases_in_title_and_snippet():
    normalizer = _build_normalizer()
    raw_job = RawJobListing(
        source="remotive",
        source_job_id="1002",
        title="Backend Engineer",
        tags=["Node.js", "K8s"],
        description_text="Work with TS, Node.js, Postgres, and k8s in production.",
    )

    job = normalizer.normalize_job(raw_job)

    assert job.skills == ["kubernetes", "node", "postgresql", "typescript"]
    assert job.language == "en"


def test_normalizer_detects_turkish_language_from_title_characters():
    normalizer = _build_normalizer()
    raw_job = RawJobListing(
        source="kariyer",
        source_job_id="tr-1001",
        title="Yazılım Geliştirici",
        company="Istanbul Tech",
        location_raw="Istanbul, Turkey",
    )

    job = normalizer.normalize_job(raw_job)

    assert job.language == "tr"
