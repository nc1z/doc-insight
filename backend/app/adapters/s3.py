import asyncio
from datetime import datetime
from typing import Any, Protocol, Self, cast

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.domain.ports import StoredObject

_MISSING_BUCKET = {"404", "NoSuchBucket", "NotFound"}
_BUCKET_EXISTS = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}


class ObjectStore(Protocol):
    def head_bucket(self, *, Bucket: str) -> Any: ...

    def create_bucket(
        self,
        *,
        Bucket: str,
        CreateBucketConfiguration: dict[str, str] | None = None,
    ) -> Any: ...

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> Any: ...

    def get_object(self, *, Bucket: str, Key: str) -> Any: ...

    def delete_object(self, *, Bucket: str, Key: str) -> Any: ...

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        ContinuationToken: str | None = None,
    ) -> Any: ...


class S3FileStorage:
    """Stores files through the S3 API. MinIO and AWS S3 differ only in settings."""

    def __init__(self, client: ObjectStore, bucket: str, *, region: str) -> None:
        self.bucket = bucket
        self._client = client
        self._region = region

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
            config=Config(s3={"addressing_style": "path"}),
        )
        return cls(cast(ObjectStore, client), settings.s3_bucket, region=settings.s3_region)

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._put, key, data, content_type)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get, key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete, key)

    async def list_objects(self) -> list[StoredObject]:
        return await asyncio.to_thread(self._list)

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if not _is_missing_bucket(exc):
                raise
            self._create_bucket()

    def _create_bucket(self) -> None:
        try:
            if self._region == "us-east-1":
                self._client.create_bucket(Bucket=self.bucket)
                return
            self._client.create_bucket(
                Bucket=self.bucket,
                CreateBucketConfiguration={"LocationConstraint": self._region},
            )
        except ClientError as exc:
            if _error_code(exc) not in _BUCKET_EXISTS:
                raise

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def _get(self, key: str) -> bytes:
        body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
        return bytes(body.read())

    def _delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def _list(self) -> list[StoredObject]:
        found: list[StoredObject] = []
        token: str | None = None
        while True:
            if token is None:
                page = self._client.list_objects_v2(Bucket=self.bucket)
            else:
                page = self._client.list_objects_v2(Bucket=self.bucket, ContinuationToken=token)
            for item in page.get("Contents", []):
                modified = item["LastModified"]
                if isinstance(modified, datetime):
                    found.append(StoredObject(key=str(item["Key"]), last_modified=modified))
            if not page.get("IsTruncated"):
                return found
            token = str(page["NextContinuationToken"])


def _is_missing_bucket(exc: ClientError) -> bool:
    if _error_code(exc) in _MISSING_BUCKET:
        return True
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status == 404


def _error_code(exc: ClientError) -> str:
    error = exc.response.get("Error", {})
    return str(error.get("Code", ""))
