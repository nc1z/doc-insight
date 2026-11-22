from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.domain.models import Job
from app.domain.status import DocumentStatus, JobStatus


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


@dataclass(frozen=True)
class StoredObject:
    key: str
    last_modified: datetime


@dataclass(frozen=True)
class DocumentProgress:
    status: DocumentStatus
    job_status: JobStatus
    excluded: bool
    stored: bool
    filename: str
    page_count: int | None


@dataclass(frozen=True)
class Classification:
    label: str
    score: float


class JobRepository(Protocol):
    async def create_and_enqueue(self, documents: Sequence[NewDocument]) -> Job: ...

    async def create_awaiting_input(
        self,
        documents: Sequence[NewDocument],
        rejected: Sequence[NewRejection],
    ) -> Job: ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def add_documents(
        self,
        job_id: UUID,
        documents: Sequence[NewDocument],
        rejected: Sequence[NewRejection],
    ) -> Job | None: ...

    async def confirm(self, job_id: UUID) -> Job | None: ...

    async def cancel(self, job_id: UUID) -> Job | None: ...

    async def expire_awaiting(self, older_than: datetime) -> Sequence[str]: ...

    async def storage_keys(self) -> set[str]: ...

    async def document_progress(self, document_id: UUID) -> DocumentProgress | None: ...

    async def complete_step(
        self,
        document_id: UUID,
        expected: DocumentStatus,
        target: DocumentStatus,
    ) -> bool: ...

    async def save_flag(self, document_id: UUID, flagged: bool) -> None: ...

    async def save_summary(self, document_id: UUID, summary: Mapping[str, Any]) -> None: ...

    async def consolidate(
        self,
        job_id: UUID,
        report: Mapping[str, Any] | None = None,
    ) -> bool: ...


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


class Classifier(Protocol):
    async def classify(self, text: str) -> Classification: ...


class FileStorage(Protocol):
    async def ensure_bucket(self) -> None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def list_objects(self) -> Sequence[StoredObject]: ...
