from typing import Any
from uuid import UUID

from app.domain.ports import Classifier, JobRepository, LLMProvider
from app.domain.status import DocumentStatus
from app.pipeline.models import DocumentSummary, ExtractInput
from app.pipeline.steps import (
    check_document,
    consolidate_summaries,
    extract_text,
    summarise_document,
)


class DocumentPipeline:
    """Runs one stored step. Earlier steps are recomputed without the delay."""

    def __init__(
        self,
        repository: JobRepository,
        llm: LLMProvider,
        classifier: Classifier,
        *,
        delay_seconds: float,
    ) -> None:
        self._jobs = repository
        self._llm = llm
        self._classifier = classifier
        self._delay = delay_seconds

    async def run_step(self, document_id: UUID, status: DocumentStatus) -> None:
        progress = await self._jobs.document_progress(document_id)
        if progress is None:
            return
        document = ExtractInput(filename=progress.filename, page_count=progress.page_count)
        extracted = await extract_text(
            document,
            delay_seconds=self._delay if status is DocumentStatus.EXTRACTING else 0,
        )
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
            document,
            extracted,
            checked,
            self._llm,
            delay_seconds=self._delay if status is DocumentStatus.SUMMARISING else 0,
        )
        await self._jobs.save_summary(document_id, summary.model_dump(mode="json"))

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
