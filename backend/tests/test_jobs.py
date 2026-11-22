import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.factory import _JOB_REPOSITORIES, build_job_repository
from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.core.config import Settings
from app.core.db import create_engine, create_session_factory
from app.domain.ports import NewDocument
from app.domain.status import JobStatus


def _document() -> NewDocument:
    return NewDocument(filename="notes.pdf", storage_key="jobs/notes.pdf", page_count=1)


def test_create_and_enqueue_commits_the_job_and_the_queue(migrated_database_url: str) -> None:
    asyncio.run(_commits_both(migrated_database_url))


def test_failed_enqueue_rolls_back_the_job(migrated_database_url: str) -> None:
    asyncio.run(_rolls_back(migrated_database_url))


def test_empty_upload_is_rejected() -> None:
    repository = _repository("postgresql+psycopg://localhost/unused")

    with pytest.raises(ValueError, match="at least one document"):
        asyncio.run(repository.create_and_enqueue([]))


def test_factory_rejects_an_unregistered_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(_JOB_REPOSITORIES, "procrastinate")
    engine = create_engine("postgresql+psycopg://localhost/unused")

    with pytest.raises(ValueError, match="Unknown queue provider: procrastinate"):
        build_job_repository(Settings(_env_file=None), create_session_factory(engine))


def _repository(database_url: str) -> PostgresJobRepository:
    return PostgresJobRepository(
        create_session_factory(create_engine(database_url)),
        build_queue(database_url),
    )


async def _commits_both(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document()])
        async with engine.connect() as connection:
            queued = await connection.scalar(
                text(
                    "SELECT args->>'job_id' FROM procrastinate_jobs "
                    "WHERE task_name = 'process_job' AND status = 'todo'"
                )
            )
        assert job.status is JobStatus.QUEUED
        assert [item.filename for item in job.documents] == ["notes.pdf"]
        assert queued == str(job.id)
    finally:
        await _clear(engine)
        await engine.dispose()


async def _rolls_back(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))

    async def fail(_connection: object, _job_id: object) -> None:
        raise RuntimeError("queue down")

    repository._enqueue = fail  # type: ignore[method-assign]
    try:
        await _clear(engine)
        with pytest.raises(RuntimeError, match="queue down"):
            await repository.create_and_enqueue([_document()])
        async with engine.connect() as connection:
            jobs = await connection.scalar(text("SELECT count(*) FROM jobs"))
            queued = await connection.scalar(text("SELECT count(*) FROM procrastinate_jobs"))
        assert jobs == 0
        assert queued == 0
    finally:
        await _clear(engine)
        await engine.dispose()


async def _clear(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE jobs, procrastinate_jobs RESTART IDENTITY CASCADE"))
