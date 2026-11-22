import asyncio
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

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


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _pdf_file(name: str = "notes.pdf") -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, _pdf(), "application/pdf"))


def test_valid_upload_is_queued(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    pdf = _pdf()
    with _client(migrated_database_url, storage) as client:
        response = client.post("/jobs", files=[("files", ("notes.pdf", pdf, "application/pdf"))])

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert list(storage.objects.values()) == [pdf]
    asyncio.run(_assert_queued(migrated_database_url, body["id"]))


def test_mixed_upload_waits_for_input(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    with _client(migrated_database_url, storage) as client:
        response = client.post(
            "/jobs",
            files=[
                _pdf_file("report.pdf"),
                ("files", ("notes.pdf", b"not a pdf", "text/plain")),
            ],
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_input"
    assert [item["filename"] for item in body["accepted"]] == ["report.pdf"]
    assert body["rejected"] == [
        {
            "filename": "notes.pdf",
            "code": "unsupported_type",
            "message": "The file is not a PDF.",
        }
    ]
    assert len(storage.objects) == 1
    asyncio.run(_assert_waiting(migrated_database_url, body["id"]))


def test_rejected_upload_stores_nothing(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    with _client(migrated_database_url, storage) as client:
        response = client.post("/jobs", files=[("files", ("notes.pdf", b"hello", "text/plain"))])

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Every file was rejected.",
        "details": {
            "rejected": [
                {
                    "filename": "notes.pdf",
                    "code": "unsupported_type",
                    "message": "The file is not a PDF.",
                }
            ]
        },
    }
    assert storage.objects == {}
    asyncio.run(_assert_no_job(migrated_database_url))


def test_too_many_files_stores_nothing(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    with _client(migrated_database_url, storage, max_file_count=1) as client:
        response = client.post("/jobs", files=[_pdf_file("one.pdf"), _pdf_file("two.pdf")])

    assert response.status_code == 422
    assert response.json()["code"] == "file_count_exceeded"
    assert response.json()["details"] is None
    assert storage.objects == {}
    asyncio.run(_assert_no_job(migrated_database_url))


def test_oversized_file_is_a_per_file_rejection(migrated_database_url: str) -> None:
    storage = RecordingStorage()
    with _client(migrated_database_url, storage, max_file_bytes=8) as client:
        response = client.post("/jobs", files=[_pdf_file()])

    assert response.status_code == 422
    rejected = response.json()["details"]["rejected"]
    assert rejected[0]["code"] == "file_too_large"
    assert storage.objects == {}
    asyncio.run(_assert_no_job(migrated_database_url))


def _client(
    database_url: str,
    storage: RecordingStorage,
    **limits: int,
) -> TestClient:
    application = create_app(
        Settings(_env_file=None, database_url=database_url, **limits),
        file_storage=storage,
    )
    return TestClient(application)


async def _assert_queued(database_url: str, job_id: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            status = await connection.scalar(
                text("SELECT status FROM jobs WHERE id = :id"),
                {"id": job_id},
            )
            digest = await connection.scalar(
                text("SELECT sha256 FROM documents WHERE job_id = :id"),
                {"id": job_id},
            )
            queued = await connection.scalar(
                text(
                    "SELECT count(*) FROM procrastinate_jobs "
                    "WHERE task_name = 'process_document' "
                    "AND args->>'document_id' IN ("
                    "SELECT id::text FROM documents WHERE job_id = :id"
                    ")"
                ),
                {"id": job_id},
            )
        assert status == "queued"
        assert digest is not None and len(digest) == 64
        assert queued == 1
    finally:
        await _clear(engine)
        await engine.dispose()


async def _assert_waiting(database_url: str, job_id: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            status = await connection.scalar(
                text("SELECT status FROM jobs WHERE id = :id"),
                {"id": job_id},
            )
            rows = (
                await connection.execute(
                    text(
                        "SELECT filename, status, rejection_reason, storage_key IS NULL "
                        "FROM documents WHERE job_id = :id ORDER BY filename"
                    ),
                    {"id": job_id},
                )
            ).all()
            queued = await connection.scalar(_TASKS_FOR_JOB, {"id": job_id})
        assert status == "awaiting_input"
        assert rows == [
            ("notes.pdf", "failed", "unsupported_type", True),
            ("report.pdf", "pending", None, False),
        ]
        assert queued == 0
    finally:
        await _clear(engine)
        await engine.dispose()


async def _assert_no_job(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            jobs = await connection.scalar(text("SELECT count(*) FROM jobs"))
        assert jobs == 0
    finally:
        await _clear(engine)
        await engine.dispose()


async def _clear(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE jobs, procrastinate_jobs RESTART IDENTITY CASCADE"))
