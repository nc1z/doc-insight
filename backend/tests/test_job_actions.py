import asyncio
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import create_engine
from app.main import create_app

_TASKS_FOR_JOB = text(
    """
    SELECT count(*) FROM procrastinate_jobs
    WHERE args->>'document_id' IN (
        SELECT id::text FROM documents WHERE job_id = :id
    )
    OR (task_name = 'consolidate_job' AND args->>'job_id' = CAST(:id AS text))
    """
)


class RecordingStorage:
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


def test_reupload_adds_files_and_keeps_other_rejections(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            response = client.post(
                f"/jobs/{job_id}/documents",
                files=[_pdf("extra.pdf"), _text("other.pdf")],
            )
            queued = client.get(f"/jobs/{job_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "awaiting_input"
        assert sorted(item["filename"] for item in body["documents"]) == ["extra.pdf", "report.pdf"]
        assert sorted(item["filename"] for item in body["rejected_files"]) == [
            "notes.pdf",
            "other.pdf",
        ]
        assert queued.json()["status"] == "awaiting_input"
        assert len(storage.objects) == 2
        asyncio.run(_assert_queue(migrated_database_url, job_id, 0))
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_reupload_replaces_a_rejected_file(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            response = client.post(
                f"/jobs/{created.json()['id']}/documents",
                files=[_pdf("notes.pdf")],
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "awaiting_input"
        assert sorted(item["filename"] for item in body["documents"]) == ["notes.pdf", "report.pdf"]
        assert body["rejected_files"] == []
        assert len(storage.objects) == 2
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_reupload_to_a_queued_job_conflicts(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf")])
            response = client.post(
                f"/jobs/{created.json()['id']}/documents",
                files=[_pdf("extra.pdf")],
            )

        assert response.status_code == 409
        assert response.json()["code"] == "invalid_job_state"
        assert len(storage.objects) == 1
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_confirm_queues_the_job_and_excludes_rejections(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            response = client.post(f"/jobs/{job_id}/confirm")

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert [item["filename"] for item in body["documents"]] == ["report.pdf"]
        assert [item["filename"] for item in body["excluded_files"]] == ["notes.pdf"]
        assert body["rejected_files"] == []
        assert len(storage.objects) == 1
        asyncio.run(_assert_excluded(migrated_database_url, job_id))
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_confirm_of_a_cancelled_job_conflicts(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            cancelled = client.post(f"/jobs/{job_id}/cancel")
            response = client.post(f"/jobs/{job_id}/confirm")

        assert cancelled.status_code == 200
        assert response.status_code == 409
        assert response.json()["code"] == "invalid_job_state"
        asyncio.run(_assert_queue(migrated_database_url, job_id, 0))
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_cancel_deletes_stored_files(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    try:
        with _client(migrated_database_url, storage) as client:
            created = client.post("/jobs", files=[_pdf("report.pdf"), _text("notes.pdf")])
            job_id = created.json()["id"]
            response = client.post(f"/jobs/{job_id}/cancel")
            follow = client.get(f"/jobs/{job_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert follow.json()["status"] == "cancelled"
        assert storage.objects == {}
    finally:
        asyncio.run(_clear(migrated_database_url))


def test_unknown_job_actions_are_not_found(migrated_database_url: str) -> None:
    missing = uuid4()
    with _client(migrated_database_url, RecordingStorage()) as client:
        documents = client.post(f"/jobs/{missing}/documents", files=[_pdf("extra.pdf")])
        confirm = client.post(f"/jobs/{missing}/confirm")
        cancel = client.post(f"/jobs/{missing}/cancel")

    assert documents.status_code == 404
    assert confirm.status_code == 404
    assert cancel.status_code == 404
    assert documents.json()["code"] == "not_found"


def _pdf(name: str) -> tuple[str, tuple[str, bytes, str]]:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return ("files", (name, buffer.getvalue(), "application/pdf"))


def _text(name: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, b"not a pdf", "text/plain"))


def _client(database_url: str, storage: RecordingStorage) -> TestClient:
    application = create_app(
        Settings(_env_file=None, database_url=database_url),
        file_storage=storage,
    )
    return TestClient(application)


async def _assert_queue(database_url: str, job_id: str, expected: int) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            queued = await connection.scalar(_TASKS_FOR_JOB, {"id": job_id})
        assert queued == expected
    finally:
        await engine.dispose()


async def _assert_excluded(database_url: str, job_id: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT filename, excluded, status FROM documents "
                        "WHERE job_id = :id ORDER BY filename"
                    ),
                    {"id": job_id},
                )
            ).all()
            queued = await connection.scalar(_TASKS_FOR_JOB, {"id": job_id})
        assert rows == [("notes.pdf", True, "failed"), ("report.pdf", False, "pending")]
        assert queued == 1
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
