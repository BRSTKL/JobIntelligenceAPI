from datetime import UTC, datetime
from uuid import uuid4

from app.models.schemas import EmploymentTypeEnum, JobRecord, RemoteTypeEnum, SeniorityLevelEnum
from app.services.repository import SQLiteRepository


def _memory_db_uri(filename: str) -> str:
    return f"file:{filename}-{uuid4().hex}?mode=memory&cache=shared"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _job(
    job_id: str,
    *,
    source_job_id: str,
    source_job_url: str | None,
    title: str = "Backend Engineer",
    company: str = "Acme",
) -> JobRecord:
    return JobRecord(
        id=job_id,
        source="remoteok",
        source_job_id=source_job_id,
        source_job_url=source_job_url,
        language="en",
        title=title,
        normalized_title="Backend Engineer",
        company=company,
        location_raw="Berlin, Germany",
        location_city="Berlin",
        location_country="Germany",
        remote_type=RemoteTypeEnum.remote,
        employment_type=EmploymentTypeEnum.full_time,
        seniority_level=SeniorityLevelEnum.mid,
        salary_text=None,
        description_snippet="Build Python APIs.",
        skills=["python", "fastapi"],
        posted_at=datetime(2026, 3, 20, 10, 0, tzinfo=UTC),
        freshness_days=2,
    )


def _read_rows(repository: SQLiteRepository):
    with repository._connect() as connection:
        return connection.execute("SELECT * FROM jobs ORDER BY id ASC").fetchall()


def test_repository_stores_new_job_and_reads_it_by_id():
    repository = SQLiteRepository(_memory_db_uri("repository-insert"))
    repository.initialize()

    inserted_at = datetime(2026, 3, 22, 9, 0, tzinfo=UTC)
    repository.now_provider = lambda: inserted_at

    job = _job(
        "job-1",
        source_job_id="1001",
        source_job_url="https://example.com/jobs/1001",
    )

    persisted_jobs = repository.upsert_jobs([job])
    rows = _read_rows(repository)
    stored_job = repository.get_job("job-1")

    assert len(persisted_jobs) == 1
    assert len(rows) == 1
    assert rows[0]["created_at"] == _iso(inserted_at)
    assert rows[0]["updated_at"] == _iso(inserted_at)
    assert rows[0]["last_seen_at"] == _iso(inserted_at)
    assert stored_job is not None
    assert stored_job.id == "job-1"
    assert stored_job.language == "en"
    assert str(stored_job.source_job_url) == "https://example.com/jobs/1001"


def test_repository_deduplicates_by_source_job_url_across_sources():
    repository = SQLiteRepository(_memory_db_uri("repository-dedupe"))
    repository.initialize()

    first_seen = datetime(2026, 3, 22, 9, 0, tzinfo=UTC)
    second_seen = datetime(2026, 3, 23, 11, 30, tzinfo=UTC)
    timestamps = iter([first_seen, second_seen])
    repository.now_provider = lambda: next(timestamps)

    first_job = _job(
        "job-1",
        source_job_id="1001",
        source_job_url="https://example.com/jobs/1001",
        title="Backend Engineer",
    )
    duplicate_job = _job(
        "job-2",
        source_job_id="9999",
        source_job_url="https://example.com/jobs/1001",
        title="Senior Backend Engineer",
    )
    duplicate_job.source = "remotive"

    repository.upsert_jobs([first_job])
    persisted_jobs = repository.upsert_jobs([duplicate_job])
    rows = _read_rows(repository)
    stored_job = repository.get_job("job-1")

    assert len(rows) == 1
    assert rows[0]["id"] == "job-1"
    assert rows[0]["source"] == "remotive"
    assert rows[0]["source_job_id"] == "9999"
    assert rows[0]["title"] == "Senior Backend Engineer"
    assert rows[0]["created_at"] == _iso(first_seen)
    assert rows[0]["updated_at"] == _iso(second_seen)
    assert rows[0]["last_seen_at"] == _iso(second_seen)
    assert len(persisted_jobs) == 1
    assert persisted_jobs[0].id == "job-1"
    assert stored_job is not None
    assert stored_job.source_job_id == "9999"
    assert repository.get_job("job-2") is None


def test_repository_updates_timestamps_when_a_job_is_seen_again():
    repository = SQLiteRepository(_memory_db_uri("repository-timestamps"))
    repository.initialize()

    first_seen = datetime(2026, 3, 22, 9, 0, tzinfo=UTC)
    second_seen = datetime(2026, 3, 24, 14, 15, tzinfo=UTC)
    timestamps = iter([first_seen, second_seen])
    repository.now_provider = lambda: next(timestamps)

    job = _job(
        "job-1",
        source_job_id="1001",
        source_job_url="https://example.com/jobs/1001",
    )

    repository.upsert_jobs([job])
    repository.upsert_jobs([job])
    rows = _read_rows(repository)

    assert len(rows) == 1
    assert rows[0]["created_at"] == _iso(first_seen)
    assert rows[0]["updated_at"] == _iso(second_seen)
    assert rows[0]["last_seen_at"] == _iso(second_seen)


def test_repository_falls_back_to_id_based_upsert_when_source_job_url_is_missing():
    repository = SQLiteRepository(_memory_db_uri("repository-fallback"))
    repository.initialize()

    first_seen = datetime(2026, 3, 22, 9, 0, tzinfo=UTC)
    second_seen = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)
    timestamps = iter([first_seen, second_seen])
    repository.now_provider = lambda: next(timestamps)

    partial_job = _job(
        "partial-job",
        source_job_id="partial-1",
        source_job_url=None,
        title="Platform Engineer",
    )
    updated_partial_job = _job(
        "partial-job",
        source_job_id="partial-1",
        source_job_url=None,
        title="Senior Platform Engineer",
    )

    repository.upsert_jobs([partial_job])
    repository.upsert_jobs([updated_partial_job])
    rows = _read_rows(repository)
    stored_job = repository.get_job("partial-job")

    assert len(rows) == 1
    assert rows[0]["source_job_url"] is None
    assert rows[0]["title"] == "Senior Platform Engineer"
    assert rows[0]["created_at"] == _iso(first_seen)
    assert rows[0]["updated_at"] == _iso(second_seen)
    assert rows[0]["last_seen_at"] == _iso(second_seen)
    assert stored_job is not None
    assert stored_job.source_job_url is None


def test_repository_list_recent_jobs_respects_limit():
    repository = SQLiteRepository(_memory_db_uri("repository-recent"))
    repository.initialize()

    repository.upsert_jobs(
        [
            _job("job-1", source_job_id="1001", source_job_url="https://example.com/jobs/1001", title="Alpha"),
            _job("job-2", source_job_id="1002", source_job_url="https://example.com/jobs/1002", title="Beta"),
            _job("job-3", source_job_id="1003", source_job_url="https://example.com/jobs/1003", title="Gamma"),
        ]
    )

    recent_jobs = repository.list_recent_jobs(limit=2)

    assert len(recent_jobs) == 2


def test_repository_backfills_language_for_older_databases():
    repository = SQLiteRepository(_memory_db_uri("repository-language-backfill"))

    with repository._connect() as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_job_id TEXT,
                source_job_url TEXT,
                title TEXT,
                normalized_title TEXT,
                company TEXT,
                location_raw TEXT,
                location_city TEXT,
                location_country TEXT,
                remote_type TEXT,
                employment_type TEXT,
                seniority_level TEXT,
                salary_text TEXT,
                description_snippet TEXT,
                skills_json TEXT NOT NULL,
                posted_at TEXT,
                freshness_days INTEGER,
                created_at TEXT,
                updated_at TEXT,
                last_seen_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO jobs (
                id, source, source_job_id, source_job_url, title, normalized_title, company,
                location_raw, location_city, location_country, remote_type, employment_type,
                seniority_level, salary_text, description_snippet, skills_json, posted_at,
                freshness_days, created_at, updated_at, last_seen_at
            ) VALUES (
                'legacy-job', 'kariyer', 'legacy-1', 'https://example.com/jobs/legacy',
                'Yazılım Geliştirici', 'Yazılım Geliştirici', 'Legacy Co', 'Istanbul, Turkey',
                'Istanbul', 'Turkey', 'remote', 'full_time', 'mid', NULL, 'Legacy snippet',
                '[]', NULL, NULL, '2026-03-22T09:00:00Z', '2026-03-22T09:00:00Z', '2026-03-22T09:00:00Z'
            )
            """
        )
        connection.commit()

    repository.initialize()
    stored_job = repository.get_job("legacy-job")

    assert stored_job is not None
    assert stored_job.language == "tr"
