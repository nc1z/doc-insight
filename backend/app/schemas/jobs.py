from uuid import UUID

from pydantic import BaseModel


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
