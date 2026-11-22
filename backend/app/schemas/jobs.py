from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.core.errors import ErrorBody


class QueuedJob(BaseModel):
    id: UUID
    status: str


class AcceptedDocument(BaseModel):
    id: UUID
    filename: str


class RejectedDocument(BaseModel):
    filename: str
    code: str
    message: str


class AwaitingJob(BaseModel):
    id: UUID
    status: str
    accepted: list[AcceptedDocument]
    rejected: list[RejectedDocument]


class JobProgress(BaseModel):
    completed_steps: int
    total_steps: int


class JobDocument(BaseModel):
    id: UUID
    filename: str
    status: str
    flagged: bool
    flag_reasons: list[str]
    error: ErrorBody | None
    summary: dict[str, Any] | None


class JobFile(BaseModel):
    id: UUID
    filename: str
    code: str
    message: str


class JobView(BaseModel):
    id: UUID
    status: str
    progress: JobProgress
    documents: list[JobDocument]
    rejected_files: list[JobFile]
    excluded_files: list[JobFile]
    report: dict[str, Any] | None
    error: ErrorBody | None
