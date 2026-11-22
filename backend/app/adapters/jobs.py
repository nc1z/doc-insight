from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import psycopg
from procrastinate import App
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.adapters.queue import CONSOLIDATE_JOB, PROCESS_DOCUMENT
from app.core.errors import DomainError
from app.domain.job_state import transition
from app.domain.models import Document, Job
from app.domain.ports import DocumentProgress, NewDocument, NewRejection
from app.domain.status import DocumentStatus, JobStatus


class PostgresJobRepository:
    """Persists jobs. Create and confirm enqueue one document task per stored file."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], queue: App) -> None:
        self._sessions = session_factory
        self._queue = queue

    async def create_and_enqueue(self, documents: Sequence[NewDocument]) -> Job:
        if not documents:
            raise ValueError("A queued job needs at least one document")
        async with self._sessions() as session, session.begin():
            job = Job(
                status=JobStatus.QUEUED,
                documents=[_document(item) for item in documents],
            )
            session.add(job)
            await session.flush()
            await self._enqueue_documents(await _driver_connection(session), job.documents)
        return job

    async def create_awaiting_input(
        self,
        documents: Sequence[NewDocument],
        rejected: Sequence[NewRejection],
    ) -> Job:
        if not documents:
            raise ValueError("A waiting job needs at least one accepted document")
        async with self._sessions() as session, session.begin():
            job = Job(
                status=JobStatus.AWAITING_INPUT,
                documents=[
                    *[_document(item) for item in documents],
                    *[_rejected_document(item) for item in rejected],
                ],
            )
            session.add(job)
            await session.flush()
        return job

    async def get(self, job_id: UUID) -> Job | None:
        async with self._sessions() as session:
            return await session.get(
                Job,
                job_id,
                options=[selectinload(Job.documents)],
            )

    async def add_documents(
        self,
        job_id: UUID,
        documents: Sequence[NewDocument],
        rejected: Sequence[NewRejection],
    ) -> Job | None:
        async with self._sessions() as session, session.begin():
            job = await self._locked(session, job_id)
            if job is None:
                return None
            job.status = transition(job.status, JobStatus.AWAITING_INPUT)
            job.updated_at = datetime.now(UTC)
            pending = _rejections_by_name(job)
            for document in documents:
                existing = pending.pop(document.filename, None)
                if existing is None:
                    job.documents.append(_document(document))
                else:
                    _accept(existing, document)
            for rejection in rejected:
                existing = pending.get(rejection.filename)
                if existing is None:
                    job.documents.append(_rejected_document(rejection))
                else:
                    existing.rejection_reason = rejection.code
            await session.flush()
        return job

    async def confirm(self, job_id: UUID) -> Job | None:
        async with self._sessions() as session, session.begin():
            job = await self._locked(session, job_id)
            if job is None:
                return None
            job.status = transition(job.status, JobStatus.QUEUED)
            stored = [document for document in job.documents if document.storage_key is not None]
            if not stored:
                raise DomainError(422, "validation_error", "The job has no documents to process.")
            for document in job.documents:
                if document.storage_key is None and not document.excluded:
                    document.excluded = True
            await session.flush()
            await self._enqueue_documents(await _driver_connection(session), job.documents)
        return job

    async def cancel(self, job_id: UUID) -> Job | None:
        async with self._sessions() as session, session.begin():
            job = await self._locked(session, job_id)
            if job is None:
                return None
            job.status = transition(job.status, JobStatus.CANCELLED)
            await session.flush()
        return job

    async def expire_awaiting(self, older_than: datetime) -> list[str]:
        async with self._sessions() as session, session.begin():
            found = await session.scalars(
                select(Job)
                .where(Job.status == JobStatus.AWAITING_INPUT, Job.updated_at < older_than)
                .options(selectinload(Job.documents))
                .with_for_update(of=Job)
            )
            keys: list[str] = []
            for job in found:
                job.status = transition(job.status, JobStatus.EXPIRED)
                keys.extend(
                    document.storage_key
                    for document in job.documents
                    if document.storage_key is not None
                )
            await session.flush()
        return keys

    async def document_progress(self, document_id: UUID) -> DocumentProgress | None:
        async with self._sessions() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return None
            job = await session.get(Job, document.job_id)
            if job is None:
                return None
            return DocumentProgress(
                status=document.status,
                job_status=job.status,
                excluded=document.excluded,
                stored=document.storage_key is not None,
            )

    async def complete_step(
        self,
        document_id: UUID,
        expected: DocumentStatus,
        target: DocumentStatus,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            located = await session.get(Document, document_id)
            if located is None:
                return False
            job = await self._locked(session, located.job_id)
            if job is None or job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
                return False
            document = next(item for item in job.documents if item.id == document_id)
            if document.excluded or document.storage_key is None or document.status is not expected:
                return False
            if job.status is JobStatus.QUEUED:
                job.status = transition(job.status, JobStatus.RUNNING)
            document.status = target
            if target is DocumentStatus.SUCCEEDED and _unfinished_stored(job) == 0:
                job.status = transition(job.status, JobStatus.CONSOLIDATING)
                await self._enqueue_consolidation(await _driver_connection(session), job.id)
            return True

    async def consolidate(self, job_id: UUID) -> bool:
        async with self._sessions() as session, session.begin():
            job = await self._locked(session, job_id)
            if job is None or job.status is not JobStatus.CONSOLIDATING:
                return False
            job.status = transition(job.status, JobStatus.SUCCEEDED)
            return True

    async def storage_keys(self) -> set[str]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Document.storage_key).where(Document.storage_key.is_not(None))
            )
        return {key for key in rows if key is not None}

    async def _locked(self, session: AsyncSession, job_id: UUID) -> Job | None:
        return await session.get(
            Job,
            job_id,
            options=[selectinload(Job.documents)],
            with_for_update=True,
        )

    async def _enqueue_documents(
        self,
        connection: psycopg.AsyncConnection,
        documents: Sequence[Document],
    ) -> None:
        task = self._queue.tasks[PROCESS_DOCUMENT]
        for document in documents:
            if document.storage_key is None or document.excluded:
                continue
            await task.configure(connection=connection).defer_async(document_id=str(document.id))

    async def _enqueue_consolidation(
        self,
        connection: psycopg.AsyncConnection,
        job_id: UUID,
    ) -> None:
        task = self._queue.tasks[CONSOLIDATE_JOB]
        await task.configure(connection=connection).defer_async(job_id=str(job_id))


def _unfinished_stored(job: Job) -> int:
    return sum(
        1
        for document in job.documents
        if document.storage_key is not None
        and not document.excluded
        and document.status not in (DocumentStatus.SUCCEEDED, DocumentStatus.FAILED)
    )


def _rejections_by_name(job: Job) -> dict[str, Document]:
    return {
        document.filename: document
        for document in job.documents
        if document.storage_key is None and not document.excluded
    }


def _accept(document: Document, item: NewDocument) -> None:
    document.storage_key = item.storage_key
    document.sha256 = item.sha256
    document.page_count = item.page_count
    document.status = DocumentStatus.PENDING
    document.rejection_reason = None


def _rejected_document(item: NewRejection) -> Document:
    return Document(
        filename=item.filename,
        status=DocumentStatus.FAILED,
        rejection_reason=item.code,
    )


def _document(item: NewDocument) -> Document:
    return Document(
        filename=item.filename,
        storage_key=item.storage_key,
        sha256=item.sha256,
        page_count=item.page_count,
        status=DocumentStatus.PENDING,
    )


async def _driver_connection(session: AsyncSession) -> psycopg.AsyncConnection:
    bind = await session.connection()
    raw = await bind.get_raw_connection()
    connection = raw.driver_connection
    if not isinstance(connection, psycopg.AsyncConnection):
        raise TypeError("The database connection is not a psycopg async connection")
    return connection
