from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_ENV_KEYS = (
    "DATABASE_URL",
    "QUEUE_PROVIDER",
    "STORAGE_PROVIDER",
    "S3_ENDPOINT",
    "S3_BUCKET",
    "S3_REGION",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "MAX_FILE_BYTES",
    "MAX_PAGE_COUNT",
    "MAX_FILE_COUNT",
    "AWAITING_INPUT_TIMEOUT_SECONDS",
    "ORPHAN_MAX_AGE_SECONDS",
    "MAINTENANCE_CRON",
    "MOCK_STEP_DELAY_SECONDS",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_TIMEOUT_SECONDS",
    "LLM_OUTPUT_RETRIES",
    "STEP_TIMEOUT_SECONDS",
    "CHUNK_TOKEN_BUDGET",
    "CLASSIFIER_PROVIDER",
    "CLASSIFIER_MODEL",
    "CLASSIFIER_BASE_URL",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLASSIFIER_API_KEY",
    "CLASSIFIER_TIMEOUT_SECONDS",
    "CLASSIFIER_FLAG_THRESHOLD",
    "SYSTEM_PROMPTS_PATH",
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    settings = Settings(
        _env_file=None,
        classifier_api_key="test-key",
        cloudflare_account_id="acct",
    )

    assert settings.llm_provider == "mock"
    assert settings.llm_model == "glm-4.7"
    assert settings.llm_output_retries == 2
    assert settings.classifier_provider == "cloudflare"
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.classifier_api_key.get_secret_value() == "test-key"
    assert settings.max_file_bytes == 20 * 1024 * 1024
    assert settings.awaiting_input_timeout_seconds == 24 * 60 * 60
    assert settings.orphan_max_age_seconds == 60 * 60
    assert settings.maintenance_cron == "*/15 * * * *"
    assert settings.mock_step_delay_seconds == 1
    assert settings.step_timeout_seconds == 60
    assert settings.chunk_token_budget == 2048
    assert settings.classifier_flag_threshold == 0.7
    assert settings.classifier_model == "typesafe/jev"
    assert settings.classifier_base_url == "https://api.cloudflare.com/client/v4"
    assert settings.cloudflare_account_id == "acct"
    assert settings.system_prompts_path.name == "prompts.yaml"
    assert settings.queue_provider == "procrastinate"
    assert settings.storage_provider == "s3"
    assert settings.s3_endpoint == "http://localhost:9000"
    assert settings.s3_bucket == "doc-insight"
    assert settings.s3_access_key.get_secret_value() == "docinsight"
    assert settings.s3_secret_key.get_secret_value() == "docinsight"


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("MAX_FILE_COUNT", "3")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "15")

    settings = Settings(_env_file=None, classifier_provider="mock")

    assert settings.max_file_count == 3
    assert settings.llm_timeout_seconds == 15


def test_cloudflare_summary_requires_api_key_and_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValidationError, match="LLM_API_KEY and CLOUDFLARE_ACCOUNT_ID"):
        Settings(_env_file=None, llm_provider="cloudflare", classifier_provider="mock")


def test_cloudflare_summary_accepts_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    settings = Settings(
        _env_file=None,
        classifier_provider="mock",
        llm_provider="cloudflare",
        llm_api_key="test-key",
        cloudflare_account_id="acct",
    )

    assert settings.llm_api_key.get_secret_value() == "test-key"
    assert settings.llm_model == "glm-4.7"


def test_cloudflare_requires_api_key_and_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValidationError, match="CLASSIFIER_API_KEY and CLOUDFLARE_ACCOUNT_ID"):
        Settings(_env_file=None, classifier_provider="cloudflare")


def test_jev_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValidationError, match="CLASSIFIER_API_KEY"):
        Settings(_env_file=None, classifier_provider="jev")


def test_limits_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_file_count=0)


def test_env_example_lists_every_setting() -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    names = {
        line.split("=", 1)[0]
        for line in example.read_text().splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    }

    settings_names = {name.upper() for name in Settings.model_fields}
    compose_only = {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "TEST_POSTGRES_USER",
        "TEST_POSTGRES_PASSWORD",
        "TEST_POSTGRES_DB",
    }

    assert settings_names <= names
    assert names - settings_names == compose_only
