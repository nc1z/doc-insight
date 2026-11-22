import asyncio
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.core.config import Settings
from app.core.db import create_engine, create_session_factory
from app.domain.failures import StepFailure
from app.domain.ports import NewDocument
from app.domain.status import DocumentStatus, JobStatus
from app.main import create_app
from app.worker.processing import retry_delay, run_document


def test_retry_delay_is_full_jitter(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[float, float]] = []

    def uniform(low: float, high: float) -> float:
        seen.append((low, high))
        return high

    monkeypatch.setattr("app.worker.processing.random.uniform", uniform)

    assert retry_delay(1) == 1
    assert retry_delay(2) == 2
    assert retry_delay(3) == 4
    assert seen == [(0, 1), (0, 2), (0, 4)]


def test_a_step_timeout_fails_that_document_after_three_attempts(
    migrated_database_url: str,
) -> None:
    asyncio.run(_times_out(migrated_database_url))


def test_a_permanent_failure_is_not_retried(migrated_database_url: str) -> None:
    asyncio.run(_permanent(migrated_database_url))


def test_an_unexpected_step_error_retries_then_fails_that_document(
    migrated_database_url: str,
) -> None:
    asyncio.run(_unexpected(migrated_database_url))


def test_a_failed_document_waits_while_the_other_keeps_processing(
    migrated_database_url: str,
) -> None:
    asyncio.run(_analyst_decides(migrated_database_url))


async def _times_out(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    calls = 0
    slept: list[float] = []

    async def hang(_document_id: UUID, _status: DocumentStatus) -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(30)

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("notes.pdf")])
        await run_document(
            repository,
            job.documents[0].id,
            perform=hang,
            step_timeout=0.05,
            sleep=sleep,
        )
        loaded = await repository.get(job.id)
        assert loaded is not None
        assert calls == 3
        assert len(slept) == 2
        assert loaded.status is JobStatus.AWAITING_INPUT
        assert loaded.documents[0].status is DocumentStatus.FAILED
        assert loaded.documents[0].rejection_reason == "step_timeout"
        assert await _consolidations(engine, str(job.id)) == 0
    finally:
        await _clear(engine)
        await engine.dispose()


async def _permanent(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    calls = 0

    async def unreadable(_document_id: UUID, _status: DocumentStatus) -> None:
        nonlocal calls
        calls += 1
        raise StepFailure("unreadable_document", permanent=True)

    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("notes.pdf")])
        await run_document(repository, job.documents[0].id, perform=unreadable, sleep=_no_sleep)
        loaded = await repository.get(job.id)
        assert loaded is not None
        assert calls == 1
        assert loaded.documents[0].status is DocumentStatus.FAILED
        assert loaded.documents[0].rejection_reason == "unreadable_document"
        assert loaded.status is JobStatus.AWAITING_INPUT
    finally:
        await _clear(engine)
        await engine.dispose()


async def _unexpected(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    calls = 0

    async def crash(_document_id: UUID, _status: DocumentStatus) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider down")

    try:
        await _clear(engine)
        job = await repository.create_and_enqueue([_document("notes.pdf")])
        await run_document(repository, job.documents[0].id, perform=crash, sleep=_no_sleep)
        loaded = await repository.get(job.id)
        assert loaded is not None
        assert calls == 3
        assert loaded.status is JobStatus.AWAITING_INPUT
        assert loaded.documents[0].rejection_reason == "step_failed"
        assert await _consolidations(engine, str(job.id)) == 0
    finally:
        await _clear(engine)
        await engine.dispose()


async def _analyst_decides(database_url: str) -> None:
    engine = create_engine(database_url)
    repository = PostgresJobRepository(create_session_factory(engine), build_queue(database_url))
    try:
        await _clear(engine)
        with _client(database_url) as client:
            created = client.post("/jobs", files=[_pdf("a.pdf"), _pdf("b.pdf")])
            job_id = created.json()["id"]
            documents = {
                item["filename"]: item["id"]
                for item in client.get(f"/jobs/{job_id}").json()["documents"]
            }

            async def fail_a(document_id: UUID, status: DocumentStatus) -> None:
                if status is DocumentStatus.EXTRACTING and str(document_id) == documents["a.pdf"]:
                    raise StepFailure("unreadable_document", permanent=True)

            await run_document(
                repository,
                UUID(documents["a.pdf"]),
                perform=fail_a,
                sleep=_no_sleep,
            )
            early = client.post(f"/jobs/{job_id}/retry")
            assert early.status_code == 202
            assert early.json()["status"] == "running"
            reset = next(item for item in early.json()["documents"] if item["filename"] == "a.pdf")
            assert reset["status"] == "pending"
            assert reset["error"] is None
            await run_document(
                repository,
                UUID(documents["a.pdf"]),
                perform=fail_a,
                sleep=_no_sleep,
            )
            running = client.get(f"/jobs/{job_id}").json()
            failed = next(item for item in running["documents"] if item["filename"] == "a.pdf")
            other = next(item for item in running["documents"] if item["filename"] == "b.pdf")
            assert running["status"] == "running"
            assert failed["status"] == "failed"
            assert failed["error"]["code"] == "unreadable_document"
            assert failed["error"]["message"] == "The document could not be read."
            assert other["status"] == "pending"
            assert await _consolidations(engine, job_id) == 0

            await run_document(repository, UUID(documents["b.pdf"]))
            waiting = client.get(f"/jobs/{job_id}").json()
            assert waiting["status"] == "awaiting_input"
            assert await _consolidations(engine, job_id) == 0

            retried = client.post(f"/jobs/{job_id}/retry")
            assert retried.status_code == 202
            body = retried.json()
            assert body["status"] == "queued"
            reset = next(item for item in body["documents"] if item["filename"] == "a.pdf")
            assert reset["status"] == "pending"
            assert reset["error"] is None

            await run_document(
                repository,
                UUID(documents["a.pdf"]),
                perform=fail_a,
                sleep=_no_sleep,
            )
            await run_document(repository, UUID(documents["b.pdf"]))
            paused = client.get(f"/jobs/{job_id}").json()
            assert paused["status"] == "awaiting_input"

            continued = client.post(f"/jobs/{job_id}/confirm")
            assert continued.status_code == 202
            report = continued.json()
            assert report["status"] == "consolidating"
            assert [item["filename"] for item in report["documents"]] == ["b.pdf"]
            assert [item["filename"] for item in report["excluded_files"]] == ["a.pdf"]
            assert await _consolidations(engine, job_id) == 1
    finally:
        await _clear(engine)
        await engine.dispose()


async def _no_sleep(_seconds: float) -> None:
    return None


def _document(filename: str) -> NewDocument:
    return NewDocument(filename=filename, storage_key=f"jobs/{filename}", page_count=1)


def _pdf(name: str) -> tuple[str, tuple[str, bytes, str]]:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return ("files", (name, buffer.getvalue(), "application/pdf"))


def _client(database_url: str) -> TestClient:
    application = create_app(
        Settings(_env_file=None, database_url=database_url),
        file_storage=_Storage(),
    )
    return TestClient(application)


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        del self.objects[key]

    async def list_objects(self) -> list[object]:
        return []


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
