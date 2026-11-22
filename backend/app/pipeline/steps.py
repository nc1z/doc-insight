import asyncio
import json
from collections.abc import Sequence

from app.domain.ports import Classifier, LLMProvider
from app.pipeline.extract import extract_pdf_pages
from app.pipeline.models import (
    CheckResult,
    ConsolidatedReport,
    DocumentSummary,
    ExtractedText,
    ExtractInput,
)


async def extract_text(
    document: ExtractInput,
    data: bytes,
    *,
    delay_seconds: float,
) -> ExtractedText:
    await asyncio.sleep(delay_seconds)
    pages = await asyncio.to_thread(extract_pdf_pages, data)
    return ExtractedText(pages=pages)


async def check_document(
    text: ExtractedText,
    classifier: Classifier,
    *,
    delay_seconds: float,
    chunks: Sequence[str] | None = None,
    flag_threshold: float = 0.7,
) -> CheckResult:
    await asyncio.sleep(delay_seconds)
    units = list(chunks) if chunks is not None else [page.text for page in text.pages]
    readable = [unit for unit in units if unit.strip()]
    scores = [await classifier.injection_probability(unit) for unit in readable]
    score = max(scores, default=0.0)
    document_type = await classifier.document_type("\n".join(readable))
    flagged = score > flag_threshold
    return CheckResult(
        flagged=flagged,
        label="injection" if flagged else "benign",
        score=score,
        document_type=document_type,
    )


async def summarise_document(
    document: ExtractInput,
    text: ExtractedText,
    check: CheckResult,
    llm: LLMProvider,
    *,
    delay_seconds: float,
) -> DocumentSummary:
    await asyncio.sleep(delay_seconds)
    body = "\n".join(page.text for page in text.pages)
    prompt = (
        "summarise\n"
        f"filename: {document.filename}\n"
        f"flagged: {check.flagged}\n"
        f"document_type: {check.document_type}\n"
        f"text: {body}"
    )
    return DocumentSummary.model_validate_json(await llm.complete(prompt))


async def consolidate_summaries(
    summaries: list[DocumentSummary],
    *,
    flagged_documents: list[str],
    excluded_files: list[str],
    llm: LLMProvider,
    delay_seconds: float,
) -> ConsolidatedReport:
    await asyncio.sleep(delay_seconds)
    prompt = (
        "consolidate\n"
        f"filenames: {json.dumps([item.title for item in summaries])}\n"
        f"flagged: {json.dumps(flagged_documents)}\n"
        f"excluded: {json.dumps(excluded_files)}"
    )
    return ConsolidatedReport.model_validate_json(await llm.complete(prompt))
