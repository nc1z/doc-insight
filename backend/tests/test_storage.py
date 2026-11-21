import asyncio
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
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        body, _content_type = self.objects[Key]
        return {"Body": _Body(body)}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, str]:
        del self.objects[Key]
        return {}


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
