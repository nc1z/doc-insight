import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from uuid import UUID

from app.domain.failures import StepFailure
from app.domain.ports import JobRepository
from app.domain.status import DocumentStatus, JobStatus

logger = logging.getLogger("app.worker")

_MAX_ATTEMPTS = 3
_RETRY_BASE_SECONDS = 1.0


class PipelineRunner(Protocol):
    async def run_step(self, document_id: UUID, status: DocumentStatus) -> None: ...

    async def build_report(self, job_id: UUID) -> dict[str, Any]: ...


_pipeline: PipelineRunner | None = None

StepPerformer = Callable[[UUID, DocumentStatus], Awaitable[None]]
Sleep = Callable[[float], Awaitable[None]]

_AFTER: dict[DocumentStatus, DocumentStatus] = {
    DocumentStatus.EXTRACTING: DocumentStatus.CHECKING,
    DocumentStatus.CHECKING: DocumentStatus.SUMMARISING,
    DocumentStatus.SUMMARISING: DocumentStatus.SUCCEEDED,
}
_ACTIVE = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})
_FINISHED = frozenset({DocumentStatus.SUCCEEDED, DocumentStatus.FAILED})


async def perform_step(document_id: UUID, status: DocumentStatus) -> None:
    if _pipeline is None:
        return
    await _pipeline.run_step(document_id, status)


def retry_delay(attempt: int, *, base: float = _RETRY_BASE_SECONDS) -> float:
    """Full jitter over an exponential cap. `attempt` is the attempt that just failed."""
    return random.uniform(0, base * 2 ** (attempt - 1))


async def run_document(
    repository: JobRepository,
    document_id: UUID,
    *,
    perform: StepPerformer | None = None,
    step_timeout: float = 60,
    max_attempts: int = _MAX_ATTEMPTS,
    sleep: Sleep = asyncio.sleep,
) -> None:
    action = perform if perform is not None else perform_step
    while True:
        progress = await repository.document_progress(document_id)
        if progress is None or progress.excluded or not progress.stored:
            return
        if progress.status in _FINISHED or progress.job_status not in _ACTIVE:
            return
        if progress.status is DocumentStatus.PENDING:
            wrote = await repository.complete_step(
                document_id,
                DocumentStatus.PENDING,
                DocumentStatus.EXTRACTING,
            )
            if not wrote:
                return
            continue
        target = _AFTER.get(progress.status)
        if target is None:
            return
        failed = await _attempt(
            repository,
            document_id,
            progress.status,
            action,
            step_timeout,
            max_attempts,
            sleep,
        )
        if failed:
            return
        wrote = await repository.complete_step(document_id, progress.status, target)
        if not wrote:
            again = await repository.document_progress(document_id)
            if again is not None and again.status is not progress.status:
                continue
            return
        logger.info("stored document %s status %s", document_id, target.value)
        if target is DocumentStatus.SUCCEEDED:
            return


async def _attempt(
    repository: JobRepository,
    document_id: UUID,
    status: DocumentStatus,
    action: StepPerformer,
    step_timeout: float,
    max_attempts: int,
    sleep: Sleep,
) -> bool:
    """Run one step until it succeeds or the document is marked failed."""
    failure = StepFailure("step_failed")
    for attempt in range(1, max_attempts + 1):
        try:
            await asyncio.wait_for(action(document_id, status), step_timeout)
        except TimeoutError:
            failure = StepFailure("step_timeout")
        except StepFailure as exc:
            failure = exc
        except Exception:
            logger.exception("document %s step %s failed", document_id, status.value)
            failure = StepFailure("step_failed")
        else:
            return False
        logger.warning(
            "document %s step %s attempt %s failed: %s",
            document_id,
            status.value,
            attempt,
            failure.code,
        )
        if failure.permanent or attempt == max_attempts:
            await repository.fail_document(document_id, failure.code)
            return True
        await sleep(retry_delay(attempt))
    return True


async def run_consolidation(repository: JobRepository, job_id: UUID) -> None:
    job = await repository.get(job_id)
    if job is None or job.status is not JobStatus.CONSOLIDATING:
        return
    report = await _pipeline.build_report(job_id) if _pipeline is not None else None
    if await repository.consolidate(job_id, report):
        logger.info("consolidated job %s", job_id)


def bind_pipeline(pipeline: PipelineRunner | None) -> None:
    global _pipeline
    _pipeline = pipeline
