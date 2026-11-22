from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.models import Job


@dataclass(frozen=True)
class NewDocument:
    filename: str
    storage_key: str
    sha256: str | None = None
    page_count: int | None = None


@dataclass(frozen=True)
class NewRejection:
    filename: str
    code: str


class JobRepository(Protocol):
    async def create_and_enqueue(self, documents: Sequence[NewDocument]) -> Job: ...

    async def create_awaiting_input(
        self,
        documents: Sequence[NewDocument],
        rejected: Sequence[NewRejection],
    ) -> Job: ...

    async def get(self, job_id: UUID) -> Job | None: ...


class FileStorage(Protocol):
    async def ensure_bucket(self) -> None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...
