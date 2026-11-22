import asyncio
import json
from collections.abc import Sequence

from app.domain.ports import Classifier, LLMProvider, LLMRequest
from app.pipeline.datamark import datamark, datamark_values
from app.pipeline.extract import extract_pdf_pages
from app.pipeline.models import (
    CheckResult,
    ChunkSummary,
    ConsolidatedReport,
    DocumentSummary,
    ExtractedText,
    ExtractInput,
    PageChunk,
)
from app.pipeline.prompts import SystemPromptCatalog


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
    score = 0.0
    winning = ""
    for unit in readable:
        unit_score = await classifier.injection_probability(unit)
        if unit_score > score:
            score = unit_score
            winning = unit
    document_type = await classifier.document_type("\n".join(readable))
    flagged = score > flag_threshold
    return CheckResult(
        flagged=flagged,
        label="injection" if flagged else "benign",
        score=score,
        document_type=document_type,
        excerpt=winning[:240] if flagged else "",
    )


def render_chunk_prompt(
    prompts: SystemPromptCatalog,
    *,
    filename: str,
    page: int,
    text: str,
) -> LLMRequest:
    return prompts.get("chunk_output").for_call(
        {"filename": filename, "page": str(page), "chunk_text": datamark(text)}
    )


async def summarise_document(
    document: ExtractInput,
    text: ExtractedText,
    check: CheckResult,
    llm: LLMProvider,
    prompts: SystemPromptCatalog,
    chunks: Sequence[PageChunk],
    *,
    delay_seconds: float,
) -> DocumentSummary:
    await asyncio.sleep(delay_seconds)
    outputs: list[ChunkSummary] = []
    for chunk in chunks:
        if not chunk.text.strip():
            continue
        outputs.append(
            await llm.complete(
                render_chunk_prompt(
                    prompts,
                    filename=document.filename,
                    page=chunk.page,
                    text=chunk.text,
                ),
                ChunkSummary,
            )
        )
    request = prompts.get("document_combine").for_call(
        {
            "filename": document.filename,
            "document_type": check.document_type,
            "flagged": "true" if check.flagged else "false",
            "chunk_outputs": json.dumps(
                [datamark_values(item.model_dump(mode="json")) for item in outputs]
            ),
            "excerpts": _excerpts(text, chunks),
        }
    )
    return await llm.complete(request, DocumentSummary)


async def consolidate_summaries(
    summaries: list[DocumentSummary],
    *,
    flagged_documents: list[str],
    excluded_files: list[str],
    llm: LLMProvider,
    prompts: SystemPromptCatalog,
    delay_seconds: float,
) -> ConsolidatedReport:
    await asyncio.sleep(delay_seconds)
    marked = [datamark_values(item.model_dump(mode="json")) for item in summaries]
    request = prompts.get("consolidation").for_call(
        {
            "summaries": json.dumps(marked),
            "flagged": json.dumps(flagged_documents),
            "excluded": json.dumps(excluded_files),
        }
    )
    return await llm.complete(request, ConsolidatedReport)


def _excerpts(text: ExtractedText, chunks: Sequence[PageChunk]) -> str:
    sources = [(chunk.page, chunk.text) for chunk in chunks if chunk.text.strip()]
    if not sources:
        sources = [(page.page, page.text) for page in text.pages if page.text.strip()]
    lines: list[str] = []
    for page, body in sources:
        marked = datamark(body)
        if marked:
            lines.append(f"page {page}: {marked}")
    return "\n".join(lines)
