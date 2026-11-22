from uuid import UUID

from procrastinate import App

from app.adapters.queue import CONSOLIDATE_JOB, PROCESS_DOCUMENT
from app.domain.ports import JobRepository
from app.worker.processing import (
    run_consolidation,
    run_document,
    settle_consolidation,
    settle_document,
)

_jobs: JobRepository | None = None
_step_timeout = 60.0


def bind_jobs(repository: JobRepository | None) -> None:
    global _jobs
    _jobs = repository


def bind_step_timeout(seconds: float) -> None:
    global _step_timeout
    _step_timeout = seconds


def register_processing(application: App) -> None:
    @application.task(name=PROCESS_DOCUMENT)
    async def process_document(document_id: str) -> None:
        repository = _require()
        document = UUID(document_id)
        try:
            await run_document(repository, document, step_timeout=_step_timeout)
        finally:
            await settle_document(repository, document)

    @application.task(name=CONSOLIDATE_JOB)
    async def consolidate_job(job_id: str) -> None:
        repository = _require()
        job = UUID(job_id)
        try:
            await run_consolidation(repository, job)
        finally:
            await settle_consolidation(repository, job)


def _require() -> JobRepository:
    if _jobs is None:
        raise RuntimeError("The worker has no job repository")
    return _jobs
