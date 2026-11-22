import hashlib
from collections.abc import Sequence
from pathlib import PurePath
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.adapters.factory import get_file_storage, get_job_repository
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.domain.ports import FileStorage, JobRepository, NewDocument, NewRejection
from app.domain.validation import (
    AcceptedFile,
    FileRejection,
    IncomingFile,
    default_strategies,
    validate_files,
)
from app.schemas.jobs import AcceptedDocument, AwaitingJob, QueuedJob, RejectedDocument

router = APIRouter()


@router.post("/jobs")
async def create_job(
    files: Annotated[list[UploadFile], File()],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
    jobs: Annotated[JobRepository, Depends(get_job_repository)],
) -> JSONResponse:
    incoming = [await _incoming_file(upload) for upload in files]
    result = validate_files(
        incoming,
        default_strategies(
            max_file_bytes=settings.max_file_bytes,
            max_page_count=settings.max_page_count,
            max_file_count=settings.max_file_count,
        ),
    )
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


def _rejected_body(item: FileRejection) -> dict[str, str]:
    return {"filename": item.filename, "code": item.code.value, "message": item.message}


def _rejected_document(item: FileRejection) -> RejectedDocument:
    return RejectedDocument(filename=item.filename, code=item.code.value, message=item.message)
