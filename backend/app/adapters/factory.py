from collections.abc import Callable

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.adapters.s3 import S3FileStorage
from app.core.config import Settings
from app.domain.ports import FileStorage, JobRepository

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
    return PostgresJobRepository(session_factory, build_queue(settings.database_url))


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
