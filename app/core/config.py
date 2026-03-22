from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


class SettingsValidationError(ValueError):
    """Raised when application settings are missing or invalid."""


def load_env_file(env_path: str | os.PathLike[str] = ".env") -> None:
    """Load a simple .env file without overriding existing environment variables."""
    path = Path(env_path)
    if not path.is_file():
        return

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SettingsValidationError(
                f"Invalid .env entry on line {line_number}: expected KEY=VALUE format."
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            raise SettingsValidationError(
                f"Invalid .env entry on line {line_number}: missing environment variable name."
            )
        os.environ.setdefault(key, value)


def _get_int_env(name: str, default: int) -> int:
    """Read an integer environment variable and fail clearly on invalid input."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value.strip())
    except ValueError:
        raise SettingsValidationError(f"{name} must be an integer.")


def _get_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated environment variable into a tuple of values."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    parsed_values = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    return parsed_values


def get_bootstrap_log_level(default: str = "INFO") -> str:
    """Return a safe logging level before full settings validation runs."""
    raw_value = os.getenv("LOG_LEVEL", default)
    candidate = raw_value.strip().upper() if raw_value else default
    return candidate if candidate in VALID_LOG_LEVELS else default


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    app_name: str = "Job Intelligence API"
    app_version: str = "0.1.0"
    app_description: str = (
        "Developer-ready API for builders of job boards, career products, matching apps, "
        "and hiring analytics tools. Turn public job listings into searchable, structured "
        "job intelligence without building your own ingestion, cleanup, normalization, "
        "and duplicate-handling pipeline."
    )
    sqlite_db_path: str = "data/jobs.db"
    source_name: str = "remoteok"
    source_base_url: str = "https://remoteok.com/json"
    http_timeout_seconds: int = 15
    cache_ttl_seconds: int = 300
    default_page_size: int = 10
    max_page_size: int = 50
    port: int = 8000
    log_level: str = "INFO"
    api_keys: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env_path: str | os.PathLike[str] = ".env") -> "Settings":
        """Create a settings object from environment variables."""
        load_env_file(env_path)
        defaults = cls()
        settings = cls(
            app_name=os.getenv("APP_NAME", defaults.app_name),
            app_version=os.getenv("APP_VERSION", defaults.app_version),
            app_description=os.getenv("APP_DESCRIPTION", defaults.app_description),
            sqlite_db_path=os.getenv("SQLITE_DB_PATH", defaults.sqlite_db_path),
            source_name=os.getenv("SOURCE_NAME", defaults.source_name),
            source_base_url=os.getenv("SOURCE_BASE_URL", defaults.source_base_url),
            http_timeout_seconds=_get_int_env("HTTP_TIMEOUT_SECONDS", defaults.http_timeout_seconds),
            cache_ttl_seconds=_get_int_env("CACHE_TTL_SECONDS", defaults.cache_ttl_seconds),
            default_page_size=_get_int_env("DEFAULT_PAGE_SIZE", defaults.default_page_size),
            max_page_size=_get_int_env("MAX_PAGE_SIZE", defaults.max_page_size),
            port=_get_int_env("PORT", defaults.port),
            log_level=os.getenv("LOG_LEVEL", defaults.log_level),
            api_keys=_get_csv_env("API_KEYS", defaults.api_keys),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Validate the settings object and raise a clear error when invalid."""
        errors: list[str] = []

        self.app_name = self.app_name.strip()
        self.app_version = self.app_version.strip()
        self.app_description = self.app_description.strip()
        self.sqlite_db_path = self.sqlite_db_path.strip()
        self.source_name = self.source_name.strip()
        self.source_base_url = self.source_base_url.strip()
        self.log_level = self.log_level.strip().upper()

        self._validate_required_text("APP_NAME", self.app_name, errors)
        self._validate_required_text("APP_VERSION", self.app_version, errors)
        self._validate_required_text("APP_DESCRIPTION", self.app_description, errors)
        self._validate_required_text("SQLITE_DB_PATH", self.sqlite_db_path, errors)
        self._validate_required_text("SOURCE_NAME", self.source_name, errors)
        self._validate_required_text("SOURCE_BASE_URL", self.source_base_url, errors)

        self._validate_positive_int("HTTP_TIMEOUT_SECONDS", self.http_timeout_seconds, errors)
        self._validate_positive_int("CACHE_TTL_SECONDS", self.cache_ttl_seconds, errors)
        self._validate_positive_int("DEFAULT_PAGE_SIZE", self.default_page_size, errors)
        self._validate_positive_int("MAX_PAGE_SIZE", self.max_page_size, errors)
        self._validate_port(errors)
        self._validate_source_url(errors)
        self._validate_log_level(errors)

        if self.default_page_size > self.max_page_size:
            errors.append("DEFAULT_PAGE_SIZE must be less than or equal to MAX_PAGE_SIZE.")

        if errors:
            message = "Invalid application settings:\n- " + "\n- ".join(errors)
            raise SettingsValidationError(message)

    @staticmethod
    def _validate_required_text(name: str, value: str, errors: list[str]) -> None:
        if not value:
            errors.append(f"{name} must not be empty.")

    @staticmethod
    def _validate_positive_int(name: str, value: int, errors: list[str]) -> None:
        if not isinstance(value, int) or value <= 0:
            errors.append(f"{name} must be a positive integer.")

    def _validate_port(self, errors: list[str]) -> None:
        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            errors.append("PORT must be an integer between 1 and 65535.")

    def _validate_source_url(self, errors: list[str]) -> None:
        parsed = urlparse(self.source_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("SOURCE_BASE_URL must be a valid http:// or https:// URL.")

    def _validate_log_level(self, errors: list[str]) -> None:
        if self.log_level not in VALID_LOG_LEVELS:
            valid_levels = ", ".join(sorted(VALID_LOG_LEVELS))
            errors.append(f"LOG_LEVEL must be one of: {valid_levels}.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object for the running application."""
    return Settings.from_env()
