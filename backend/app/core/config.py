from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent

StorageProvider = Literal["s3"]
QueueProvider = Literal["procrastinate"]
LlmProvider = Literal["mock", "openai_compatible"]
ClassifierProvider = Literal["mock", "cloudflare", "jev"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://docinsight:docinsight@localhost:5432/docinsight"
    queue_provider: QueueProvider = "procrastinate"
    storage_provider: StorageProvider = "s3"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = Field(default="doc-insight", min_length=1)
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr = SecretStr("docinsight")
    s3_secret_key: SecretStr = SecretStr("docinsight")

    max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_page_count: int = Field(default=100, gt=0)
    max_file_count: int = Field(default=10, gt=0)
    awaiting_input_timeout_seconds: int = Field(default=24 * 60 * 60, gt=0)
    orphan_max_age_seconds: int = Field(default=60 * 60, gt=0)
    maintenance_cron: str = Field(default="*/15 * * * *", min_length=1)
    mock_step_delay_seconds: float = Field(default=1, ge=0)

    llm_provider: LlmProvider = "mock"
    llm_model: str = Field(default="glm-4.7", min_length=1)
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = Field(default=60, gt=0)
    step_timeout_seconds: float = Field(default=60, gt=0)
    chunk_token_budget: int = Field(default=2048, gt=0)

    classifier_provider: ClassifierProvider = "cloudflare"
    classifier_model: str = Field(default="typesafe/jev", min_length=1)
    classifier_base_url: str = Field(
        default="https://api.cloudflare.com/client/v4",
        min_length=1,
    )
    cloudflare_account_id: str = ""
    classifier_api_key: SecretStr = SecretStr("")
    classifier_timeout_seconds: float = Field(default=30, gt=0)
    classifier_flag_threshold: float = Field(default=0.7, ge=0, le=1)
    system_prompts_path: Path = Path("app/pipeline/prompts.yaml")

    @model_validator(mode="after")
    def hosted_providers_need_credentials(self) -> Self:
        if self.llm_provider == "openai_compatible":
            missing = [
                name
                for name, present in (
                    ("LLM_BASE_URL", self.llm_base_url),
                    ("LLM_API_KEY", self.llm_api_key.get_secret_value()),
                )
                if not present
            ]
            if missing:
                required = " and ".join(missing)
                raise ValueError(f"{required} is required when LLM_PROVIDER is openai_compatible")
        if self.classifier_provider == "jev" and not self.classifier_api_key.get_secret_value():
            raise ValueError("CLASSIFIER_API_KEY is required when CLASSIFIER_PROVIDER is jev")
        if self.classifier_provider == "cloudflare":
            missing = [
                name
                for name, present in (
                    ("CLASSIFIER_API_KEY", self.classifier_api_key.get_secret_value()),
                    ("CLOUDFLARE_ACCOUNT_ID", self.cloudflare_account_id),
                )
                if not present
            ]
            if missing:
                required = " and ".join(missing)
                raise ValueError(f"{required} is required when CLASSIFIER_PROVIDER is cloudflare")
        if not self.system_prompts_path.is_absolute():
            self.system_prompts_path = _BACKEND_DIR / self.system_prompts_path
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
