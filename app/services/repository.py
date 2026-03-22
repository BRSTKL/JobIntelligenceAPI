from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.models.schemas import JobRecord

TURKISH_TITLE_CHARACTERS = set("çğıöşüÇĞİÖŞÜı")


class SQLiteRepository:
    """A lightweight SQLite repository for storing normalized jobs."""

    def __init__(
        self,
        db_path: str,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db_path = db_path
        self._use_uri = db_path.startswith("file:")
        self._shared_memory = self._use_uri and "mode=memory" in db_path
        self._keepalive_connection: sqlite3.Connection | None = None
        self.now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def initialize(self) -> None:
        if self._shared_memory and self._keepalive_connection is None:
            # Shared in-memory SQLite databases disappear when the last connection closes,
            # so tests keep one connection open for the lifetime of the repository.
            self._keepalive_connection = self._connect()

        if not self._use_uri:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        connection = self._keepalive_connection or self._connect()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_job_id TEXT,
                source_job_url TEXT,
                language TEXT,
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
        self._ensure_timestamp_columns(connection)
        self._ensure_language_column(connection)
        self._backfill_timestamp_columns(connection)
        self._backfill_language_column(connection)
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_source_url
            ON jobs (source, source_job_url)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_source_job_url
            ON jobs (source_job_url)
            """
        )
        connection.commit()

        if connection is not self._keepalive_connection:
            connection.close()

    def health_check(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def upsert_jobs(self, jobs: list[JobRecord]) -> list[JobRecord]:
        if not jobs:
            return []

        persisted_jobs: list[JobRecord] = []
        with self._connect() as connection:
            for job in jobs:
                persisted_jobs.append(self._upsert_job(connection, job))
            connection.commit()
        return persisted_jobs

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY
                    CASE WHEN freshness_days IS NULL THEN 1 ELSE 0 END,
                    freshness_days ASC,
                    title ASC
                """
            ).fetchall()

        return [self._row_to_job(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, uri=self._use_uri, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _upsert_job(self, connection: sqlite3.Connection, job: JobRecord) -> JobRecord:
        """Insert or update one job while preserving a canonical internal ID."""
        existing_row = self._find_existing_row(connection, job)
        if existing_row is None:
            return self._insert_job(connection, job)
        return self._update_existing_job(connection, existing_row, job)

    def _find_existing_row(self, connection: sqlite3.Connection, job: JobRecord) -> sqlite3.Row | None:
        """Find an existing row using URL-first deduplication and ID as a fallback."""
        if job.source_job_url:
            row = self._find_row_by_source_job_url(connection, str(job.source_job_url))
            if row is not None:
                return row
        return connection.execute("SELECT * FROM jobs WHERE id = ?", (job.id,)).fetchone()

    def _find_row_by_source_job_url(
        self,
        connection: sqlite3.Connection,
        source_job_url: str,
    ) -> sqlite3.Row | None:
        """Return the oldest matching row for a source URL regardless of source name."""
        return connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE source_job_url = ?
            ORDER BY created_at ASC, rowid ASC
            LIMIT 1
            """,
            (source_job_url,),
        ).fetchone()

    def _insert_job(self, connection: sqlite3.Connection, job: JobRecord) -> JobRecord:
        """Insert a brand-new persisted job row."""
        timestamp = self._current_timestamp()
        payload = self._build_insert_payload(job, timestamp)
        connection.execute(
            """
            INSERT INTO jobs (
                id,
                source,
                source_job_id,
                source_job_url,
                language,
                title,
                normalized_title,
                company,
                location_raw,
                location_city,
                location_country,
                remote_type,
                employment_type,
                seniority_level,
                salary_text,
                description_snippet,
                skills_json,
                posted_at,
                freshness_days,
                created_at,
                updated_at,
                last_seen_at
            )
            VALUES (
                :id,
                :source,
                :source_job_id,
                :source_job_url,
                :language,
                :title,
                :normalized_title,
                :company,
                :location_raw,
                :location_city,
                :location_country,
                :remote_type,
                :employment_type,
                :seniority_level,
                :salary_text,
                :description_snippet,
                :skills_json,
                :posted_at,
                :freshness_days,
                :created_at,
                :updated_at,
                :last_seen_at
            )
            """,
            payload,
        )
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job.id,)).fetchone()
        return self._row_to_job(row)

    def _update_existing_job(
        self,
        connection: sqlite3.Connection,
        existing_row: sqlite3.Row,
        job: JobRecord,
    ) -> JobRecord:
        """Update an existing job row while keeping the original ID and created_at."""
        payload = self._build_update_payload(existing_row, job, self._current_timestamp())
        connection.execute(
            """
            UPDATE jobs
            SET
                source = :source,
                source_job_id = :source_job_id,
                source_job_url = :source_job_url,
                language = :language,
                title = :title,
                normalized_title = :normalized_title,
                company = :company,
                location_raw = :location_raw,
                location_city = :location_city,
                location_country = :location_country,
                remote_type = :remote_type,
                employment_type = :employment_type,
                seniority_level = :seniority_level,
                salary_text = :salary_text,
                description_snippet = :description_snippet,
                skills_json = :skills_json,
                posted_at = :posted_at,
                freshness_days = :freshness_days,
                created_at = :created_at,
                updated_at = :updated_at,
                last_seen_at = :last_seen_at
            WHERE id = :persisted_id
            """,
            payload,
        )
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (payload["persisted_id"],)).fetchone()
        return self._row_to_job(row)

    def _job_to_row(self, job: JobRecord) -> dict[str, object]:
        payload = job.model_dump(mode="json")
        payload["skills_json"] = json.dumps(payload.pop("skills"))
        return payload

    def _build_insert_payload(self, job: JobRecord, timestamp: str) -> dict[str, object]:
        """Build the row payload for a new insert."""
        payload = self._job_to_row(job)
        payload["created_at"] = timestamp
        payload["updated_at"] = timestamp
        payload["last_seen_at"] = timestamp
        return payload

    def _build_update_payload(
        self,
        existing_row: sqlite3.Row,
        job: JobRecord,
        timestamp: str,
    ) -> dict[str, object]:
        """Build the row payload for an update while preserving persistence metadata."""
        payload = self._job_to_row(job)
        payload["persisted_id"] = existing_row["id"]
        payload["created_at"] = existing_row["created_at"] or timestamp
        payload["updated_at"] = timestamp
        payload["last_seen_at"] = timestamp
        return payload

    def _ensure_timestamp_columns(self, connection: sqlite3.Connection) -> None:
        """Add timestamp columns for older databases that predate persistence metadata."""
        existing_columns = self._get_column_names(connection)
        for column_name in ("created_at", "updated_at", "last_seen_at"):
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} TEXT")

    def _ensure_language_column(self, connection: sqlite3.Connection) -> None:
        """Add the language column for older databases that predate language detection."""
        existing_columns = self._get_column_names(connection)
        if "language" not in existing_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN language TEXT")

    def _backfill_timestamp_columns(self, connection: sqlite3.Connection) -> None:
        """Populate missing timestamp values so older rows remain readable."""
        timestamp = self._current_timestamp()
        connection.execute("UPDATE jobs SET created_at = ? WHERE created_at IS NULL", (timestamp,))
        connection.execute("UPDATE jobs SET updated_at = created_at WHERE updated_at IS NULL")
        connection.execute("UPDATE jobs SET last_seen_at = updated_at WHERE last_seen_at IS NULL")

    def _backfill_language_column(self, connection: sqlite3.Connection) -> None:
        """Populate missing language values using the stored title text."""
        rows = connection.execute("SELECT id, title FROM jobs WHERE language IS NULL").fetchall()
        for row in rows:
            connection.execute(
                "UPDATE jobs SET language = ? WHERE id = ?",
                (self._detect_language(row["title"]), row["id"]),
            )

    def _get_column_names(self, connection: sqlite3.Connection) -> set[str]:
        """Return the current jobs table column names."""
        rows = connection.execute("PRAGMA table_info(jobs)").fetchall()
        return {row["name"] for row in rows}

    def _current_timestamp(self) -> str:
        """Return a UTC timestamp string for persistence bookkeeping."""
        current_time = self.now_provider()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        else:
            current_time = current_time.astimezone(UTC)
        return current_time.isoformat().replace("+00:00", "Z")

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        payload = dict(row)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        payload.pop("last_seen_at", None)
        payload["skills"] = json.loads(payload.pop("skills_json") or "[]")
        return JobRecord.model_validate(payload)

    @staticmethod
    def _detect_language(title: str | None) -> str:
        """Mirror the simple tr/en title heuristic for repository backfills."""
        title_text = title or ""
        if any(character in TURKISH_TITLE_CHARACTERS for character in title_text):
            return "tr"
        return "en"
