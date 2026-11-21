from enum import StrEnum


class JobStatus(StrEnum):
    AWAITING_INPUT = "awaiting_input"
    QUEUED = "queued"
    RUNNING = "running"
    CONSOLIDATING = "consolidating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHECKING = "checking"
    SUMMARISING = "summarising"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
