import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text

from app.adapters.jobs import PostgresJobRepository
from app.adapters.maintenance import (
    DELETE_ORPHAN_FILES,
    EXPIRE_AWAITING_JOBS,
    delete_orphans_configured,
    expire_configured,
)
from app.adapters.queue import build_queue
from app.core.config import Settings
from app.core.db import create_engine, create_session_factory
from app.domain.maintenance import delete_orphan_files, expire_waiting_jobs
from app.domain.ports import StoredObject
from app.main import create_app


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, datetime]] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, datetime.now(UTC))

    async def get(self, key: str) -> bytes:
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        del self.objects[key]

    async def list_objects(self) -> list[StoredObject]:
        return [
            StoredObject(key=key, last_modified=modified)
            for key, (_, modified) in self.objects.items()
        ]


def test_old_waiting_job_expires_and_loses_its_files(migrated_database_url: str) -> None:
    storage = MemoryStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            asyncio.run(_age(migrated_database_url, job_id))
            asyncio.run(_expire(migrated_database_url, storage))
            response = client.get(f"/jobs/{job_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "expired"
        assert storage.objects == {}
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_recent_waiting_job_stays_open(migrated_database_url: str) -> None:
    storage = MemoryStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            asyncio.run(_expire(migrated_database_url, storage))
            response = client.get(f"/jobs/{job_id}")

        assert response.json()["status"] == "awaiting_input"
        assert len(storage.objects) == 1
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_reupload_resets_the_expiry_clock(migrated_database_url: str) -> None:
    storage = MemoryStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            asyncio.run(_age(migrated_database_url, job_id))
            client.post(f"/jobs/{job_id}/documents", files=[_pdf("extra.pdf")])
            asyncio.run(_expire(migrated_database_url, storage))
            response = client.get(f"/jobs/{job_id}")

        assert response.json()["status"] == "awaiting_input"
        assert len(storage.objects) == 2
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_old_queued_job_is_not_expired(migrated_database_url: str) -> None:
    storage = MemoryStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf")])
            job_id = created.json()["id"]
            asyncio.run(_age(migrated_database_url, job_id))
            asyncio.run(_expire(migrated_database_url, storage))
            response = client.get(f"/jobs/{job_id}")

        assert response.json()["status"] == "queued"
        assert len(storage.objects) == 1
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_orphan_cleanup_deletes_only_old_unreferenced_files(migrated_database_url: str) -> None:
    storage = MemoryStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            client.post("/jobs", files=[_pdf("report.pdf")])
        referenced = next(iter(storage.objects))
        storage.objects["old-orphan"] = (b"old", datetime.now(UTC) - timedelta(hours=2))
        storage.objects["new-orphan"] = (b"new", datetime.now(UTC))
        asyncio.run(_delete_orphans(migrated_database_url, storage))

        assert referenced in storage.objects
        assert "old-orphan" not in storage.objects
        assert "new-orphan" in storage.objects
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_short_configured_timeout_expires_the_job_and_deletes_orphans(
    migrated_database_url: str,
) -> None:
    storage = MemoryStorage()
    settings = Settings(
        _env_file=None,
        database_url=migrated_database_url,
        awaiting_input_timeout_seconds=1,
        orphan_max_age_seconds=1,
    )
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            asyncio.run(_age(migrated_database_url, job_id, "2 seconds"))
            storage.objects["old-orphan"] = (b"old", datetime.now(UTC) - timedelta(seconds=2))
            storage.objects["new-orphan"] = (b"new", datetime.now(UTC))
            asyncio.run(_run_configured(settings, storage))
            response = client.get(f"/jobs/{job_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "expired"
        assert list(storage.objects) == ["new-orphan"]
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_maintenance_tasks_use_the_configured_schedule() -> None:
    cron = "0 * * * *"
    application = build_queue("postgresql://localhost/unused", maintenance_cron=cron)
    scheduled = {
        name: task.cron
        for (name, _periodic_id), task in application.periodic_registry.periodic_tasks.items()
    }

    assert scheduled == {EXPIRE_AWAITING_JOBS: cron, DELETE_ORPHAN_FILES: cron}


def _pdf(name: str) -> tuple[str, tuple[str, bytes, str]]:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return ("files", (name, buffer.getvalue(), "application/pdf"))


def _text(name: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, b"not a pdf", "text/plain"))


def _client(database_url: str, storage: MemoryStorage) -> TestClient:
    application = create_app(
        Settings(_env_file=None, database_url=database_url),
        file_storage=storage,
    )
    return TestClient(application)


def _cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(hours=24)


async def _expire(database_url: str, storage: MemoryStorage) -> None:
    engine = create_engine(database_url)
    try:
        repository = PostgresJobRepository(
            create_session_factory(engine),
            build_queue(database_url),
        )
        await expire_waiting_jobs(repository, storage, older_than=_cutoff())
    finally:
        await engine.dispose()


async def _delete_orphans(database_url: str, storage: MemoryStorage) -> None:
    engine = create_engine(database_url)
    try:
        repository = PostgresJobRepository(
            create_session_factory(engine),
            build_queue(database_url),
        )
        await delete_orphan_files(
            repository, storage, older_than=datetime.now(UTC) - timedelta(hours=1)
        )
    finally:
        await engine.dispose()


async def _run_configured(settings: Settings, storage: MemoryStorage) -> None:
    queue = build_queue(settings.database_url)
    await expire_configured(queue, settings, storage)
    await delete_orphans_configured(queue, settings, storage)


async def _age(database_url: str, job_id: str, interval: str = "25 hours") -> None:
    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE jobs SET updated_at = now() - cast(:interval as interval) WHERE id = :id"
                ),
                {"id": job_id, "interval": interval},
            )
    finally:
        await engine.dispose()


async def _clear(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE jobs, procrastinate_jobs RESTART IDENTITY CASCADE")
            )
    finally:
        await engine.dispose()
