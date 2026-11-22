from datetime import UTC, datetime, timedelta

from procrastinate import App

from app.adapters.factory import build_file_storage
from app.adapters.jobs import PostgresJobRepository
from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.domain.maintenance import delete_orphan_files, expire_waiting_jobs

EXPIRE_AWAITING_JOBS = "expire_awaiting_jobs"
DELETE_ORPHAN_FILES = "delete_orphan_files"


def register_maintenance(application: App, *, cron: str) -> None:
    @application.periodic(cron=cron)
    @application.task(name=EXPIRE_AWAITING_JOBS, queueing_lock=EXPIRE_AWAITING_JOBS)
    async def expire_awaiting_jobs(timestamp: int) -> None:
        del timestamp
        await _expire(application)

    @application.periodic(cron=cron)
    @application.task(name=DELETE_ORPHAN_FILES, queueing_lock=DELETE_ORPHAN_FILES)
    async def delete_orphans(timestamp: int) -> None:
        del timestamp
        await _delete_orphans(application)


async def _expire(queue: App) -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.awaiting_input_timeout_seconds)
    engine = create_engine(settings.database_url)
    try:
        repository = PostgresJobRepository(create_session_factory(engine), queue)
        await expire_waiting_jobs(
            repository,
            build_file_storage(settings),
            older_than=cutoff,
        )
    finally:
        await engine.dispose()


async def _delete_orphans(queue: App) -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.orphan_max_age_seconds)
    engine = create_engine(settings.database_url)
    try:
        repository = PostgresJobRepository(create_session_factory(engine), queue)
        await delete_orphan_files(
            repository,
            build_file_storage(settings),
            older_than=cutoff,
        )
    finally:
        await engine.dispose()
