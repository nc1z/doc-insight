import asyncio
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import CONSOLIDATE_JOB, PROCESS_DOCUMENT, build_queue
from app.api.jobs import _job_view
from app.core.db import create_engine, create_session_factory
from app.domain.ports import NewDocument
from app.domain.status import DocumentStatus, JobStatus
from app.worker.processing import bind_pipeline, run_consolidation, run_document
from app.worker.tasks import bind_jobs


def test_processing_tasks_are_registered() -> None:
    application = build_queue("postgresql://localhost/unused")

    assert PROCESS_DOCUMENT in application.tasks
    assert CONSOLIDATE_JOB in application.tasks


def test_a_document_task_reaches_consolidation_and_a_retry_does_not_repeat_it(
    migrated_database_url: str,
) -> None:
    asyncio.run(_reaches_consolidation(migrated_database_url))


def test_a_retry_runs_only_the_steps_after_the_stored_status(migrated_database_url: str) -> None:
    asyncio.run(_resumes(migrated_database_url))


def test_the_last_document_starts_consolidation_once(migrated_database_url: str) -> None:
    asyncio.run(_fan_in(migrated_database_url))


def test_a_timed_out_consolidation_fails_the_job(migrated_database_url: str) -> None:
    asyncio.run(_consolidation_timeout(migrated_database_url))


def test_a_document_task_that_stops_early_fails_that_document(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.worker.tasks.run_document", stop)
    asyncio.run(_document_task_stops(migrated_database_url))


def test_a_consolidation_that_stops_early_fails_the_job(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.worker.tasks.run_consolidation", stop)
    asyncio.run(_consolidation_stops(migrated_database_url))


async def _reaches_consolidation(database_url: str) -> None:
    engine = create_engine(database_url)
    queue = build_queue(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), queue)
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("notes.pdf")])
        bind_jobs(repository)
        await queue.tasks[PROCESS_DOCUMENT](document_id=str(job.documents[0].id))
        loaded = await repository.get(job.id)
        assert loaded is not None
        assert loaded.status is JobStatus.CONSOLIDATING
        assert loaded.documents[0].status is DocumentStatus.SUCCEEDED
        assert await _consolidations(engine, str(job.id)) == 1

        await queue.tasks[PROCESS_DOCUMENT](document_id=str(job.documents[0].id))
        assert await _consolidations(engine, str(job.id)) == 1
        await queue.tasks[CONSOLIDATE_JOB](job_id=str(job.id))
        finished = await repository.get(job.id)
        assert finished is not None
        assert finished.status is JobStatus.SUCCEEDED
        await queue.tasks[CONSOLIDATE_JOB](job_id=str(job.id))
        repeated = await repository.get(job.id)
        assert repeated is not None
        assert repeated.status is JobStatus.SUCCEEDED
    finally:
        bind_jobs(None)
        await _clear(engine)
        await engine.dispose()


async def _resumes(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    seen: list[DocumentStatus] = []

    async def perform(_document_id: UUID, status: DocumentStatus) -> None:
        seen.append(status)

    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("notes.pdf")])
        document_id = job.documents[0].id
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE documents SET status = 'summarising' WHERE id = :id"),
                {"id": document_id},
            )
        await run_document(repository, document_id, perform=perform)
        loaded = await repository.get(job.id)
        assert loaded is not None
        assert seen == [DocumentStatus.SUMMARISING]
        assert loaded.status is JobStatus.CONSOLIDATING
        assert loaded.documents[0].status is DocumentStatus.SUCCEEDED
    finally:
        await _clear(engine)
        await engine.dispose()


async def _fan_in(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("a.pdf"), _document("b.pdf")])
        ids = {item.filename: item.id for item in job.documents}
        await run_document(repository, ids["a.pdf"])
        halfway = await repository.get(job.id)
        assert halfway is not None
        assert halfway.status is JobStatus.RUNNING
        assert await _consolidations(engine, str(job.id)) == 0

        await run_document(repository, ids["b.pdf"])
        ready = await repository.get(job.id)
        assert ready is not None
        assert ready.status is JobStatus.CONSOLIDATING
        assert await _consolidations(engine, str(job.id)) == 1

        await run_document(repository, ids["b.pdf"])
        assert await _consolidations(engine, str(job.id)) == 1
        await run_consolidation(repository, job.id)
        finished = await repository.get(job.id)
        assert finished is not None
        assert finished.status is JobStatus.SUCCEEDED
        await run_consolidation(repository, job.id)
        assert await _consolidations(engine, str(job.id)) == 1
    finally:
        await _clear(engine)
        await engine.dispose()


class _TimeoutReport:
    async def run_step(self, document_id: UUID, status: DocumentStatus) -> None:
        return

    async def build_report(self, job_id: UUID) -> dict[str, object]:
        raise TimeoutError


async def _consolidation_timeout(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    bind_pipeline(_TimeoutReport())
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("desk-note.pdf")])
        document_id = job.documents[0].id
        await run_document(repository, document_id)
        await run_consolidation(repository, job.id)
        failed = await repository.get(job.id)
        assert failed is not None
        assert failed.status is JobStatus.FAILED
        assert failed.failure_reason == "step_timeout"
        error = _job_view(failed).error
        assert error is not None
        assert error.code == "step_timeout"
        assert error.message == "The step timed out."
    finally:
        bind_pipeline(None)
        await _clear(engine)
        await engine.dispose()


async def _document_task_stops(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    bind_jobs(repository)
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("desk-note.pdf")])
        await build_queue(database_url).tasks[PROCESS_DOCUMENT](
            document_id=str(job.documents[0].id)
        )
        failed = await repository.get(job.id)
        assert failed is not None
        assert failed.status is JobStatus.AWAITING_INPUT
        assert failed.documents[0].status is DocumentStatus.FAILED
        assert failed.documents[0].rejection_reason == "step_failed"
    finally:
        bind_jobs(None)
        await _clear(engine)
        await engine.dispose()


async def _consolidation_stops(database_url: str) -> None:
    engine = create_engine(database_url)
    queue = build_queue(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), queue)
    bind_jobs(repository)
    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("desk-note.pdf")])
        await run_document(repository, job.documents[0].id)
        await queue.tasks[CONSOLIDATE_JOB](job_id=str(job.id))
        failed = await repository.get(job.id)
        assert failed is not None
        assert failed.status is JobStatus.FAILED
        error = _job_view(failed).error
        assert error is not None
        assert error.code == "step_failed"
        assert error.message == "The step failed."
    finally:
        bind_jobs(None)
        await _clear(engine)
        await engine.dispose()


def _document(filename: str) -> NewDocument:
    return NewDocument(filename=filename, storage_key=f"jobs/{filename}", page_count=1)


async def _consolidations(engine: AsyncEngine, job_id: str) -> int:
    async with engine.connect() as connection:
        count = await connection.scalar(
            text(
                "SELECT count(*) FROM procrastinate_jobs "
                "WHERE task_name = 'consolidate_job' AND args->>'job_id' = :id"
            ),
            {"id": job_id},
        )
    return int(count or 0)


async def _clear(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE jobs, procrastinate_jobs RESTART IDENTITY CASCADE"))
