import asyncio
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import create_engine
from app.main import create_app
from tests.doubles import IdleFileStorage


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


def test_queued_job_shows_pending_documents(migrated_database_url: str) -> None:
    with _client(migrated_database_url) as client:
        created = client.post(
            "/jobs", files=[("files", ("desk-note.pdf", _pdf(), "application/pdf"))]
        )
        job_id = created.json()["id"]
        response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert body["status"] == "queued"
    assert body["progress"] == {"completed_steps": 0, "total_steps": 1}
    assert body["documents"] == [
        {
            "id": body["documents"][0]["id"],
            "filename": "desk-note.pdf",
            "status": "pending",
            "flagged": False,
            "error": None,
            "summary": None,
        }
    ]
    assert body["rejected_files"] == []
    assert body["excluded_files"] == []
    assert body["report"] is None
    assert body["error"] is None
    asyncio.run(_clear(migrated_database_url))


def test_mixed_job_lists_the_rejected_file(migrated_database_url: str) -> None:
    with _client(migrated_database_url) as client:
        created = client.post(
            "/jobs",
            files=[
                ("files", ("desk-note.pdf", _pdf(), "application/pdf")),
                ("files", ("notes.pdf", b"not a pdf", "text/plain")),
            ],
        )
        response = client.get(f"/jobs/{created.json()['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_input"
    assert [item["filename"] for item in body["documents"]] == ["desk-note.pdf"]
    assert body["rejected_files"] == [
        {
            "id": body["rejected_files"][0]["id"],
            "filename": "notes.pdf",
            "code": "unsupported_type",
            "message": "The file is not a PDF.",
        }
    ]
    assert body["excluded_files"] == []
    assert body["progress"] == {"completed_steps": 0, "total_steps": 1}
    asyncio.run(_clear(migrated_database_url))


def test_unknown_job_uses_the_error_schema(migrated_database_url: str) -> None:
    with _client(migrated_database_url) as client:
        response = client.get(f"/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "message": "The job was not found.",
        "details": None,
    }


def test_openapi_schema_matches_the_job_view() -> None:
    application = create_app(
        Settings(_env_file=None, llm_provider="mock", classifier_provider="mock"),
        file_storage=IdleFileStorage(),
    )
    with TestClient(application) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/jobs/{id}"]["get"]
    view = schema["components"]["schemas"]["JobView"]
    document = schema["components"]["schemas"]["JobDocument"]
    assert set(view["properties"]) == {
        "id",
        "status",
        "progress",
        "documents",
        "rejected_files",
        "excluded_files",
        "report",
        "error",
    }
    assert set(document["properties"]) == {
        "id",
        "filename",
        "status",
        "flagged",
        "error",
        "summary",
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/JobView"
    )
    assert operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorBody"
    )


def _client(database_url: str) -> TestClient:
    application = create_app(
        Settings(_env_file=None, database_url=database_url),
        file_storage=RecordingStorage(),
    )
    return TestClient(application)


async def _clear(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE jobs, procrastinate_jobs RESTART IDENTITY CASCADE")
            )
    finally:
        await engine.dispose()
