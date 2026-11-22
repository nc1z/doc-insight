import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.adapters.factory import _ADAPTERS, build_file_storage, get_file_storage
from app.adapters.s3 import S3FileStorage
from app.core.config import Settings
from app.main import create_app
from tests.doubles import IdleFileStorage


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    def __init__(self, *, head_code: str | None = None) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.modified: dict[str, datetime] = {}
        self.created: list[dict[str, str] | None] = []
        self._head_code = head_code
        self._exists = head_code is None

    def head_bucket(self, *, Bucket: str) -> dict[str, str]:
        if self._exists:
            return {}
        code = self._head_code or "404"
        raise ClientError({"Error": {"Code": code}}, "HeadBucket")

    def create_bucket(
        self,
        *,
        Bucket: str,
        CreateBucketConfiguration: dict[str, str] | None = None,
    ) -> dict[str, str]:
        self.created.append(CreateBucketConfiguration)
        self._exists = True
        return {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> dict[str, str]:
        self.objects[Key] = (Body, ContentType)
        self.modified[Key] = datetime.now(UTC)
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        body, _content_type = self.objects[Key]
        return {"Body": _Body(body)}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, str]:
        del self.objects[Key]
        self.modified.pop(Key, None)
        return {}

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        ContinuationToken: str | None = None,
    ) -> dict[str, Any]:
        keys = sorted(self.objects)
        start = int(ContinuationToken or "0")
        chunk = keys[start : start + 1]
        next_start = start + len(chunk)
        truncated = next_start < len(keys)
        return {
            "Contents": [{"Key": key, "LastModified": self.modified[key]} for key in chunk],
            "IsTruncated": truncated,
            "NextContinuationToken": str(next_start) if truncated else None,
        }


def _storage(client: FakeS3, *, region: str = "us-east-1") -> S3FileStorage:
    return S3FileStorage(client, "doc-insight", region=region)


def test_missing_bucket_is_created() -> None:
    client = FakeS3(head_code="404")
    asyncio.run(_storage(client).ensure_bucket())

    assert client.created == [None]


def test_existing_bucket_is_left_alone() -> None:
    client = FakeS3()
    asyncio.run(_storage(client).ensure_bucket())

    assert client.created == []


def test_bucket_in_another_region_sets_the_location() -> None:
    client = FakeS3(head_code="NoSuchBucket")
    asyncio.run(_storage(client, region="eu-west-1").ensure_bucket())

    assert client.created == [{"LocationConstraint": "eu-west-1"}]


def test_bucket_permission_error_is_raised() -> None:
    client = FakeS3(head_code="403")

    with pytest.raises(ClientError):
        asyncio.run(_storage(client).ensure_bucket())


def test_put_get_and_delete_round_trip() -> None:
    storage = _storage(FakeS3())

    asyncio.run(storage.put("jobs/1/notes.pdf", b"%PDF", "application/pdf"))
    assert asyncio.run(storage.get("jobs/1/notes.pdf")) == b"%PDF"
    asyncio.run(storage.delete("jobs/1/notes.pdf"))

    with pytest.raises(KeyError):
        asyncio.run(storage.get("jobs/1/notes.pdf"))


def test_list_reads_every_page() -> None:
    client = FakeS3()
    storage = _storage(client)
    asyncio.run(storage.put("b.pdf", b"b", "application/pdf"))
    asyncio.run(storage.put("a.pdf", b"a", "application/pdf"))

    listed = asyncio.run(storage.list_objects())

    assert [item.key for item in listed] == ["a.pdf", "b.pdf"]
    assert listed[0].last_modified == client.modified["a.pdf"]


def test_factory_builds_the_s3_adapter() -> None:
    storage = build_file_storage(Settings(_env_file=None))

    assert isinstance(storage, S3FileStorage)
    assert storage.bucket == "doc-insight"


def test_factory_rejects_an_unregistered_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(_ADAPTERS, "s3")

    with pytest.raises(ValueError, match="Unknown storage provider: s3"):
        build_file_storage(Settings(_env_file=None))


def test_startup_creates_the_bucket() -> None:
    class RecordingStorage(IdleFileStorage):
        def __init__(self) -> None:
            self.ensured = False

        async def ensure_bucket(self) -> None:
            self.ensured = True

    storage = RecordingStorage()
    application = create_app(Settings(_env_file=None), file_storage=storage)

    with TestClient(application):
        pass

    assert storage.ensured


def test_dependency_returns_the_app_storage() -> None:
    storage = IdleFileStorage()
    application = create_app(Settings(_env_file=None), file_storage=storage)
    request = Request({"type": "http", "app": application})

    assert get_file_storage(request) is storage
