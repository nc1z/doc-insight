from typing import Any
from uuid import UUID

from app.domain.failures import StepFailure
from app.domain.ports import (
    Classifier,
    DocumentProgress,
    FileStorage,
    JobRepository,
    LLMProvider,
    StoredChunk,
    StoredPage,
)
from app.domain.status import DocumentStatus
from app.pipeline.chunk import chunk_pages
from app.pipeline.models import DocumentSummary, ExtractedText, ExtractInput, PageText
from app.pipeline.steps import (
    check_document,
    consolidate_summaries,
    extract_text,
    summarise_document,
)


class DocumentPipeline:
    """Runs one stored step. Extract saves each page and its chunks."""

    def __init__(
        self,
        repository: JobRepository,
        llm: LLMProvider,
        classifier: Classifier,
        storage: FileStorage,
        *,
        delay_seconds: float,
        chunk_token_budget: int,
    ) -> None:
        self._jobs = repository
        self._llm = llm
        self._classifier = classifier
        self._files = storage
        self._delay = delay_seconds
        self._chunk_token_budget = chunk_token_budget

    async def run_step(self, document_id: UUID, status: DocumentStatus) -> None:
        progress = await self._jobs.document_progress(document_id)
        if progress is None:
            return
        extracted = await self._pages(document_id, progress, status)
        if status is DocumentStatus.EXTRACTING:
            return
        checked = await check_document(
            extracted,
            self._classifier,
            delay_seconds=self._delay if status is DocumentStatus.CHECKING else 0,
        )
        if status is DocumentStatus.CHECKING:
            await self._jobs.save_flag(document_id, checked.flagged)
            return
        summary = await summarise_document(
            ExtractInput(filename=progress.filename, page_count=progress.page_count),
            extracted,
            checked,
            self._llm,
            delay_seconds=self._delay if status is DocumentStatus.SUMMARISING else 0,
        )
        await self._jobs.save_summary(document_id, summary.model_dump(mode="json"))

    async def _pages(
        self,
        document_id: UUID,
        progress: DocumentProgress,
        status: DocumentStatus,
    ) -> ExtractedText:
        if progress.storage_key is None:
            raise StepFailure("unreadable_document", permanent=True)
        if status is not DocumentStatus.EXTRACTING:
            stored = await self._jobs.list_pages(document_id)
            if stored:
                return ExtractedText(pages=[_page_text(page) for page in stored])
        data = await self._files.get(progress.storage_key)
        extracted = await extract_text(
            ExtractInput(filename=progress.filename, page_count=progress.page_count),
            data,
            delay_seconds=self._delay if status is DocumentStatus.EXTRACTING else 0,
        )
        await self._jobs.replace_pages(
            document_id,
            [
                StoredPage(page_number=page.page, text=page.text, needs_image=page.needs_image)
                for page in extracted.pages
            ],
        )
        await self._jobs.replace_chunks(
            document_id,
            [
                StoredChunk(
                    page_number=chunk.page,
                    position=position,
                    text=chunk.text,
                    token_count=chunk.token_count,
                )
                for position, chunk in enumerate(
                    chunk_pages(extracted.pages, self._chunk_token_budget)
                )
            ],
        )
        return extracted

    async def build_report(self, job_id: UUID) -> dict[str, Any]:
        job = await self._jobs.get(job_id)
        if job is None:
            return {}
        summaries = [
            DocumentSummary.model_validate(document.summary)
            for document in job.documents
            if document.summary is not None and document.storage_key is not None
        ]
        flagged = [
            document.filename
            for document in job.documents
            if document.flagged and document.storage_key is not None
        ]
        excluded = [document.filename for document in job.documents if document.excluded]
        report = await consolidate_summaries(
            summaries,
            flagged_documents=flagged,
            excluded_files=excluded,
            llm=self._llm,
            delay_seconds=self._delay,
        )
        return report.model_dump(mode="json")


def _page_text(page: StoredPage) -> PageText:
    return PageText(page=page.page_number, text=page.text, needs_image=page.needs_image)
