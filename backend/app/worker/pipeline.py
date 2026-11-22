import asyncio
from collections.abc import Sequence
from pathlib import Path
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
    StoredGuardrail,
    StoredPage,
)
from app.domain.status import DocumentStatus
from app.pipeline.chunk import chunk_pages
from app.pipeline.guardrails import ALONE_RULES, GuardrailFinding, scan_pdf
from app.pipeline.models import DocumentSummary, ExtractedText, ExtractInput, PageText
from app.pipeline.prompts import SystemPromptCatalog, load_system_prompts
from app.pipeline.steps import (
    check_document,
    consolidate_summaries,
    extract_text,
    summarise_document,
)


def _page_for(excerpt: str, chunks: Sequence[StoredChunk], text: ExtractedText) -> int:
    for chunk in chunks:
        if chunk.text.startswith(excerpt) or excerpt.startswith(chunk.text):
            return chunk.page_number
    for page in text.pages:
        if page.text.startswith(excerpt) or excerpt.startswith(page.text):
            return page.page
    return text.pages[0].page if text.pages else 1


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
        flag_threshold: float = 0.7,
        prompts: SystemPromptCatalog | None = None,
    ) -> None:
        self._jobs = repository
        self._llm = llm
        self._classifier = classifier
        self._files = storage
        self._delay = delay_seconds
        self._chunk_token_budget = chunk_token_budget
        self._flag_threshold = flag_threshold
        self._prompts = prompts or load_system_prompts(
            Path(__file__).resolve().parents[1] / "pipeline" / "prompts.yaml"
        )

    async def run_step(self, document_id: UUID, status: DocumentStatus) -> None:
        progress = await self._jobs.document_progress(document_id)
        if progress is None:
            return
        extracted = await self._pages(document_id, progress, status)
        if status is DocumentStatus.EXTRACTING:
            return
        stored_chunks = await self._jobs.list_chunks(document_id)
        chunk_texts = [chunk.text for chunk in stored_chunks]
        checked = await check_document(
            extracted,
            self._classifier,
            delay_seconds=self._delay if status is DocumentStatus.CHECKING else 0,
            chunks=chunk_texts or None,
            flag_threshold=self._flag_threshold,
        )
        if status is DocumentStatus.CHECKING:
            findings: list[GuardrailFinding] = []
            if progress.storage_key is not None:
                data = await self._files.get(progress.storage_key)
                findings = await asyncio.to_thread(scan_pdf, data)
            if checked.flagged:
                findings.append(
                    GuardrailFinding(
                        page_number=_page_for(checked.excerpt, stored_chunks, extracted),
                        rule="classifier",
                        excerpt=checked.excerpt,
                    )
                )
            await self._jobs.replace_guardrails(
                document_id,
                [
                    StoredGuardrail(
                        page_number=finding.page_number,
                        rule=finding.rule,
                        excerpt=finding.excerpt,
                    )
                    for finding in findings
                ],
            )
            flagged = checked.flagged or any(finding.rule in ALONE_RULES for finding in findings)
            await self._jobs.save_flag(document_id, flagged)
            return
        summary = await summarise_document(
            ExtractInput(filename=progress.filename, page_count=progress.page_count),
            extracted,
            checked,
            self._llm,
            self._prompts,
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
            prompts=self._prompts,
            delay_seconds=self._delay,
        )
        return report.model_dump(mode="json")


def _page_text(page: StoredPage) -> PageText:
    return PageText(page=page.page_number, text=page.text, needs_image=page.needs_image)
