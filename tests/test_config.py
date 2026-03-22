from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings, SettingsValidationError


ENV_NAMES = (
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "API_KEYS",
    "PORT",
    "SQLITE_DB_PATH",
    "SOURCE_NAME",
    "SOURCE_BASE_URL",
    "HTTP_TIMEOUT_SECONDS",
    "CACHE_TTL_SECONDS",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "LOG_LEVEL",
)


def _clear_settings_env(monkeypatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _env_file(name: str) -> Path:
    path = Path("test_output")
    path.mkdir(exist_ok=True)
    return path / f"{name}-{uuid4().hex}.env"


def test_settings_from_env_rejects_invalid_port(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("PORT", "not-a-number")

    with pytest.raises(SettingsValidationError, match="PORT must be an integer"):
        Settings.from_env(env_path=_env_file("invalid-port"))


def test_settings_from_env_rejects_invalid_page_size_relationship(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("DEFAULT_PAGE_SIZE", "100")
    monkeypatch.setenv("MAX_PAGE_SIZE", "50")

    with pytest.raises(SettingsValidationError, match="DEFAULT_PAGE_SIZE must be less than or equal to MAX_PAGE_SIZE"):
        Settings.from_env(env_path=_env_file("page-sizes"))


def test_settings_from_env_loads_dotenv_without_overwriting_existing_environment(
    monkeypatch,
):
    _clear_settings_env(monkeypatch)
    env_file = _env_file("dotenv-load")
    env_file.write_text(
        "\n".join(
            [
                "APP_NAME=Loaded From File",
                "PORT=9010",
                "API_KEYS=file-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_NAME", "Loaded From Environment")

    settings = Settings.from_env(env_path=env_file)

    assert settings.app_name == "Loaded From Environment"
    assert settings.port == 9010
    assert settings.api_keys == ("file-key",)
