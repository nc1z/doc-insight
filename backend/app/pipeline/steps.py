import asyncio
import json

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
) -> CheckResult:
    await asyncio.sleep(delay_seconds)
    joined = "\n".join(page.text for page in text.pages)
    classified = await classifier.classify(joined)
    return CheckResult(
        flagged=classified.label == "injection",
        label=classified.label,
        score=classified.score,
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
    prompt = f"summarise\nfilename: {document.filename}\nflagged: {check.flagged}\ntext: {body}"
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
