from uuid import UUID

from procrastinate import App

from app.adapters.queue import CONSOLIDATE_JOB, PROCESS_DOCUMENT
from app.domain.ports import JobRepository
from app.worker.processing import run_consolidation, run_document

_jobs: JobRepository | None = None


def bind_jobs(repository: JobRepository | None) -> None:
    global _jobs
    _jobs = repository


def register_processing(application: App) -> None:
    @application.task(name=PROCESS_DOCUMENT)
    async def process_document(document_id: str) -> None:
        await run_document(_require(), UUID(document_id))

    @application.task(name=CONSOLIDATE_JOB)
    async def consolidate_job(job_id: str) -> None:
        await run_consolidation(_require(), UUID(job_id))


def _require() -> JobRepository:
    if _jobs is None:
        raise RuntimeError("The worker has no job repository")
    return _jobs
