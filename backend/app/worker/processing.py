import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from app.domain.ports import JobRepository
from app.domain.status import DocumentStatus, JobStatus

logger = logging.getLogger("app.worker")

StepPerformer = Callable[[DocumentStatus], Awaitable[None]]

_NEXT: dict[DocumentStatus, DocumentStatus] = {
    DocumentStatus.PENDING: DocumentStatus.EXTRACTING,
    DocumentStatus.EXTRACTING: DocumentStatus.CHECKING,
    DocumentStatus.CHECKING: DocumentStatus.SUMMARISING,
    DocumentStatus.SUMMARISING: DocumentStatus.SUCCEEDED,
}
_ACTIVE = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})
_FINISHED = frozenset({DocumentStatus.SUCCEEDED, DocumentStatus.FAILED})


def next_status(current: DocumentStatus) -> DocumentStatus | None:
    return _NEXT.get(current)


async def perform_step(_status: DocumentStatus) -> None:
    """The pipeline fills this in. The stored status is what a retry skips."""
    return


async def run_document(
    repository: JobRepository,
    document_id: UUID,
    *,
    perform: StepPerformer | None = None,
) -> None:
    action = perform if perform is not None else perform_step
    while True:
        progress = await repository.document_progress(document_id)
        if progress is None or progress.excluded or not progress.stored:
            return
        if progress.status in _FINISHED or progress.job_status not in _ACTIVE:
            return
        target = next_status(progress.status)
        if target is None:
            return
        if target is not DocumentStatus.SUCCEEDED:
            await action(target)
        wrote = await repository.complete_step(document_id, progress.status, target)
        if not wrote:
            again = await repository.document_progress(document_id)
            if again is not None and again.status is not progress.status:
                continue
            return
        logger.info("stored document %s status %s", document_id, target.value)
        if target is DocumentStatus.SUCCEEDED:
            return


async def run_consolidation(repository: JobRepository, job_id: UUID) -> None:
    if await repository.consolidate(job_id):
        logger.info("consolidated job %s", job_id)
