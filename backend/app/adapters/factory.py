from collections.abc import Callable

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.decision_model import CloudflareClassifier, DecisionModelClassifier
from app.adapters.jobs import PostgresJobRepository
from app.adapters.mocks.mock_classifier import MockClassifier
from app.adapters.mocks.mock_llm import MockLLM
from app.adapters.mocks.mock_vision import MockPageReader
from app.adapters.queue import build_queue
from app.adapters.s3 import S3FileStorage
from app.adapters.summary_client import GatewaySummaryClient
from app.adapters.vision_client import GatewayPageReader
from app.core.config import Settings
from app.domain.ports import Classifier, FileStorage, JobRepository, LLMProvider, PageReader

StorageBuilder = Callable[[Settings], FileStorage]
JobRepositoryBuilder = Callable[[async_sessionmaker[AsyncSession], Settings], JobRepository]

_ADAPTERS: dict[str, StorageBuilder] = {
    "s3": S3FileStorage.from_settings,
}


def register_storage_adapter(provider: str, builder: StorageBuilder) -> None:
    _ADAPTERS[provider] = builder


def build_file_storage(settings: Settings) -> FileStorage:
    try:
        builder = _ADAPTERS[settings.storage_provider]
    except KeyError:
        raise ValueError(f"Unknown storage provider: {settings.storage_provider}") from None
    return builder(settings)


def get_file_storage(request: Request) -> FileStorage:
    return request.app.state.file_storage


def _postgres_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> JobRepository:
    return PostgresJobRepository(
        session_factory,
        build_queue(
            settings.database_url,
            maintenance_cron=settings.maintenance_cron,
            reclaim_cron=settings.reclaim_cron,
        ),
    )


_JOB_REPOSITORIES: dict[str, JobRepositoryBuilder] = {
    "procrastinate": _postgres_jobs,
}


def register_job_repository(provider: str, builder: JobRepositoryBuilder) -> None:
    _JOB_REPOSITORIES[provider] = builder


def build_job_repository(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> JobRepository:
    try:
        builder = _JOB_REPOSITORIES[settings.queue_provider]
    except KeyError:
        raise ValueError(f"Unknown queue provider: {settings.queue_provider}") from None
    return builder(session_factory, settings)


def get_job_repository(request: Request) -> JobRepository:
    return request.app.state.job_repository


LLMBuilder = Callable[[Settings], LLMProvider]
ClassifierBuilder = Callable[[Settings], Classifier]

_LLM_ADAPTERS: dict[str, LLMBuilder] = {
    "mock": MockLLM.from_settings,
    "cloudflare": GatewaySummaryClient.from_settings,
}
_CLASSIFIER_ADAPTERS: dict[str, ClassifierBuilder] = {
    "mock": MockClassifier.from_settings,
    "cloudflare": CloudflareClassifier.from_settings,
    "jev": DecisionModelClassifier.from_settings,
}


PageReaderBuilder = Callable[[Settings], PageReader | None]

# "off" builds nothing: the worker then skips image pages, as it did before readers existed.
_PAGE_READERS: dict[str, PageReaderBuilder] = {
    "off": lambda settings: None,
    "mock": MockPageReader.from_settings,
    "cloudflare": GatewayPageReader.from_settings,
}


def register_page_reader(provider: str, builder: PageReaderBuilder) -> None:
    _PAGE_READERS[provider] = builder


def build_page_reader(settings: Settings) -> PageReader | None:
    try:
        builder = _PAGE_READERS[settings.vision_provider]
    except KeyError:
        raise ValueError(f"Unknown vision provider: {settings.vision_provider}") from None
    return builder(settings)


def build_llm(settings: Settings) -> LLMProvider:
    try:
        builder = _LLM_ADAPTERS[settings.llm_provider]
    except KeyError:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}") from None
    return builder(settings)


def build_classifier(settings: Settings) -> Classifier:
    try:
        builder = _CLASSIFIER_ADAPTERS[settings.classifier_provider]
    except KeyError:
        raise ValueError(f"Unknown classifier provider: {settings.classifier_provider}") from None
    return builder(settings)
