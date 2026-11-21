from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent

LlmProvider = Literal["mock", "openai_compatible"]
ClassifierProvider = Literal["mock", "jev"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://docinsight:docinsight@localhost:5432/docinsight"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = Field(default="doc-insight", min_length=1)
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr = SecretStr("docinsight")
    s3_secret_key: SecretStr = SecretStr("docinsight")

    max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_page_count: int = Field(default=100, gt=0)
    max_file_count: int = Field(default=10, gt=0)

    llm_provider: LlmProvider = "mock"
    llm_model: str = Field(default="glm-4.7", min_length=1)
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: float = Field(default=60, gt=0)

    classifier_provider: ClassifierProvider = "mock"
    classifier_model: str = Field(default="jev", min_length=1)
    classifier_api_key: SecretStr = SecretStr("")
    classifier_timeout_seconds: float = Field(default=30, gt=0)

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
