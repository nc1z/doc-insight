from collections.abc import Sequence
from uuid import UUID

import psycopg
from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.queue import PROCESS_JOB
from app.domain.models import Document, Job
from app.domain.ports import NewDocument, NewRejection
from app.domain.status import DocumentStatus, JobStatus


class PostgresJobRepository:
    """Creates the job row and the Procrastinate queue row in one transaction."""

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
            await self._enqueue(await _driver_connection(session), job.id)
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

    async def _enqueue(self, connection: psycopg.AsyncConnection, job_id: UUID) -> None:
        task = self._queue.tasks[PROCESS_JOB]
        await task.configure(connection=connection).defer_async(job_id=str(job_id))


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
