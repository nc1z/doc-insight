import hashlib
from collections.abc import Sequence
from pathlib import PurePath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.adapters.factory import get_file_storage, get_job_repository
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ErrorBody
from app.domain.job_state import transition
from app.domain.models import Document, Job
from app.domain.ports import FileStorage, JobRepository, NewDocument, NewRejection
from app.domain.status import DocumentStatus, JobStatus
from app.domain.validation import (
    AcceptedFile,
    FileRejection,
    IncomingFile,
    ValidationStrategy,
    default_strategies,
    message_for,
    validate_files,
)
from app.pipeline.guardrails import FLAG_REASONS
from app.schemas.jobs import (
    AcceptedDocument,
    AwaitingJob,
    JobDocument,
    JobFile,
    JobProgress,
    JobView,
    QueuedJob,
    RejectedDocument,
)

router = APIRouter()
_STEPS_PER_DOCUMENT = 3
_COMPLETED_STEPS = {
    DocumentStatus.PENDING: 0,
    DocumentStatus.EXTRACTING: 0,
    DocumentStatus.CHECKING: 1,
    DocumentStatus.SUMMARISING: 2,
    DocumentStatus.SUCCEEDED: _STEPS_PER_DOCUMENT,
    DocumentStatus.FAILED: _STEPS_PER_DOCUMENT,
}


@router.get(
    "/jobs/{id}",
    response_model=JobView,
    responses={404: {"model": ErrorBody}},
)
async def read_job(
    id: UUID,
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobView:
    job = await jobs.get(id)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    return _job_view(job)


@router.post(
    "/jobs",
    status_code=202,
    response_model=QueuedJob,
    responses={
        201: {"model": AwaitingJob},
        422: {"model": ErrorBody},
    },
)
async def create_job(
    files: Annotated[list[UploadFile], File()],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JSONResponse:
    incoming = [await _incoming_file(upload) for upload in files]
    result = validate_files(incoming, _strategies(settings))
    if result.error is not None:
        raise DomainError(422, result.error.code.value, result.error.message)
    if not result.accepted:
        raise DomainError(
            422,
            "validation_error",
            "Every file was rejected.",
            details={"rejected": [_rejected_body(item) for item in result.rejected]},
        )

    stored = await _store_accepted(storage, result.accepted)
    if result.rejected:
        waiting = [
            NewRejection(filename=item.filename, code=item.code.value) for item in result.rejected
        ]
        job = await jobs.create_awaiting_input(stored, waiting)
        waiting_body = AwaitingJob(
            id=job.id,
            status=job.status.value,
            accepted=[
                AcceptedDocument(id=document.id, filename=document.filename)
                for document in job.documents
                if document.storage_key is not None
            ],
            rejected=[_rejected_document(item) for item in result.rejected],
        )
        return JSONResponse(status_code=201, content=waiting_body.model_dump(mode="json"))

    job = await jobs.create_and_enqueue(stored)
    queued = QueuedJob(id=job.id, status=job.status.value)
    return JSONResponse(status_code=202, content=queued.model_dump(mode="json"))


@router.post(
    "/jobs/{id}/documents",
    response_model=JobView,
    responses={404: {"model": ErrorBody}, 409: {"model": ErrorBody}, 422: {"model": ErrorBody}},
)
async def add_job_documents(
    id: UUID,
    files: Annotated[list[UploadFile], File()],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobView:
    await _require_waiting(jobs, id)
    incoming = [await _incoming_file(upload) for upload in files]
    result = validate_files(incoming, _strategies(settings))
    if result.error is not None:
        raise DomainError(422, result.error.code.value, result.error.message)
    stored = await _store_accepted(storage, result.accepted)
    rejected = [
        NewRejection(filename=item.filename, code=item.code.value) for item in result.rejected
    ]
    job = await jobs.add_documents(id, stored, rejected)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    return _job_view(job)


@router.post(
    "/jobs/{id}/confirm",
    response_model=JobView,
    status_code=202,
    responses={404: {"model": ErrorBody}, 409: {"model": ErrorBody}},
)
async def confirm_job(
    id: UUID,
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobView:
    job = await jobs.confirm(id)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    return _job_view(job)


@router.post(
    "/jobs/{id}/retry",
    response_model=JobView,
    status_code=202,
    responses={
        404: {"model": ErrorBody},
        409: {"model": ErrorBody},
        422: {"model": ErrorBody},
    },
)
async def retry_job(
    id: UUID,
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobView:
    job = await jobs.retry(id)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    return _job_view(job)


@router.post(
    "/jobs/{id}/cancel",
    response_model=JobView,
    responses={404: {"model": ErrorBody}, 409: {"model": ErrorBody}},
)
async def cancel_job(
    id: UUID,
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JobView:
    job = await jobs.cancel(id)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    for document in job.documents:
        if document.storage_key is not None:
            await storage.delete(document.storage_key)
    return _job_view(job)


async def _require_waiting(jobs: JobRepository, job_id: UUID) -> None:
    job = await jobs.get(job_id)
    if job is None:
        raise DomainError(404, "not_found", "The job was not found.")
    transition(job.status, JobStatus.AWAITING_INPUT)


def _strategies(settings: Settings) -> tuple[ValidationStrategy, ...]:
    return default_strategies(
        max_file_bytes=settings.max_file_bytes,
        max_page_count=settings.max_page_count,
        max_file_count=settings.max_file_count,
    )


async def _incoming_file(upload: UploadFile) -> IncomingFile:
    name = PurePath(upload.filename or "upload.pdf").name or "upload.pdf"
    return IncomingFile(
        filename=name,
        content_type=upload.content_type or "",
        data=await upload.read(),
    )


async def _store_accepted(
    storage: FileStorage,
    files: Sequence[AcceptedFile],
) -> list[NewDocument]:
    documents: list[NewDocument] = []
    for item in files:
        key = f"{uuid4()}/{PurePath(item.filename).name}"
        await storage.put(key, item.data, "application/pdf")
        documents.append(
            NewDocument(
                filename=item.filename,
                storage_key=key,
                sha256=hashlib.sha256(item.data).hexdigest(),
                page_count=item.page_count,
            )
        )
    return documents


def _job_view(job: Job) -> JobView:
    ordered = sorted(job.documents, key=lambda document: (document.created_at, document.filename))
    rejected: list[JobFile] = []
    excluded: list[JobFile] = []
    documents: list[JobDocument] = []
    completed = 0
    for document in ordered:
        if document.excluded:
            excluded.append(_job_file(document))
        elif document.storage_key is None:
            rejected.append(_job_file(document))
        else:
            documents.append(_job_document(document))
            completed += _COMPLETED_STEPS[document.status]
    return JobView(
        id=job.id,
        status=job.status.value,
        progress=JobProgress(
            completed_steps=completed,
            total_steps=_STEPS_PER_DOCUMENT * len(documents),
        ),
        documents=documents,
        rejected_files=rejected,
        excluded_files=excluded,
        report=job.report,
        error=_job_error(job),
    )


def _job_error(job: Job) -> ErrorBody | None:
    if job.status is not JobStatus.FAILED or job.failure_reason is None:
        return None
    return ErrorBody(code=job.failure_reason, message=message_for(job.failure_reason))


def _job_document(document: Document) -> JobDocument:
    error = None
    if document.status is DocumentStatus.FAILED and document.rejection_reason is not None:
        error = ErrorBody(
            code=document.rejection_reason,
            message=message_for(document.rejection_reason),
        )
    return JobDocument(
        id=document.id,
        filename=document.filename,
        status=document.status.value,
        flagged=document.flagged,
        flag_reasons=_flag_reasons(document),
        error=error,
        summary=document.summary,
    )


def _flag_reasons(document: Document) -> list[str]:
    if not document.flagged:
        return []
    return sorted({item.rule for item in document.guardrails if item.rule in FLAG_REASONS})


def _job_file(document: Document) -> JobFile:
    code = document.rejection_reason or "rejected"
    return JobFile(
        id=document.id,
        filename=document.filename,
        code=code,
        message=message_for(code),
    )


def _rejected_body(item: FileRejection) -> dict[str, str]:
    return {"filename": item.filename, "code": item.code.value, "message": item.message}


def _rejected_document(item: FileRejection) -> RejectedDocument:
    return RejectedDocument(filename=item.filename, code=item.code.value, message=item.message)
