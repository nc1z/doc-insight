import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.db import create_engine
from app.main import create_app
from evals.builder import FixtureLimits, build_upload

_CASES = [
    case
    for case in json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "adversarial.json").read_text()
    )["cases"]
    if case["phase"] == 1 and "ci_mock" in case["runs_in"]
]


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


@pytest.mark.parametrize("case", _CASES, ids=[case["id"] for case in _CASES])
def test_phase_one_case(case: dict[str, object], migrated_database_url: str) -> None:
    settings = Settings(_env_file=None, database_url=migrated_database_url)
    limits = FixtureLimits(
        max_file_bytes=settings.max_file_bytes,
        max_page_count=settings.max_page_count,
        max_file_count=settings.max_file_count,
    )
    step = case["steps"][0]
    storage = RecordingStorage()
    built = build_upload(step["files"], limits)
    application = create_app(settings, file_storage=storage)
    with TestClient(application) as client:
        response = client.post(
            "/jobs",
            files=[("files", (item.filename, item.data, item.content_type)) for item in built],
        )
    expect = step["expect"]
    assert response.status_code == expect["http_status"]
    body = response.json()
    if "error_code" in expect:
        assert body["code"] == expect["error_code"]
    if "rejected" in expect:
        rejected = [
            {"filename": item["filename"], "code": item["code"]}
            for item in body["details"]["rejected"]
        ]
        assert rejected == expect["rejected"]
    if expect.get("job_created") is False:
        assert storage.objects == {}
        asyncio.run(_assert_no_job(migrated_database_url))
    if "stored_files" in expect:
        assert len(storage.objects) == expect["stored_files"]


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
