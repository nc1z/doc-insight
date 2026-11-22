import asyncio
import json
from collections.abc import Sequence

from app.domain.ports import Classifier, LLMCall, LLMProvider, LLMRequest
from app.pipeline.citations import supported_points
from app.pipeline.datamark import datamark, datamark_values
from app.pipeline.extract import extract_pdf_pages
from app.pipeline.models import (
    CheckResult,
    ChunkSummary,
    ConsolidatedReport,
    DocumentSummary,
    ExtractedText,
    ExtractInput,
    NotablePoint,
    PageChunk,
    PageText,
    Section,
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
) -> tuple[DocumentSummary, list[LLMCall]]:
    await asyncio.sleep(delay_seconds)
    outputs, calls = await _chunk_summaries(document, text, llm, prompts, chunks)
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
    result = await llm.complete(request, DocumentSummary)
    calls.append(result.call)
    output = result.output
    summary = output.model_copy(
        update={
            "notable_points": supported_points(output.notable_points, text.pages),
            "sections": [
                _verified_section(section, text.pages, document.filename)
                for section in output.sections
            ],
        }
    )
    return summary, calls


async def _chunk_summaries(
    document: ExtractInput,
    text: ExtractedText,
    llm: LLMProvider,
    prompts: SystemPromptCatalog,
    chunks: Sequence[PageChunk],
) -> tuple[list[ChunkSummary], list[LLMCall]]:
    outputs: list[ChunkSummary] = []
    calls: list[LLMCall] = []
    for chunk in chunks:
        if not chunk.text.strip():
            continue
        result = await llm.complete(
            render_chunk_prompt(
                prompts,
                filename=document.filename,
                page=chunk.page,
                text=chunk.text,
            ),
            ChunkSummary,
        )
        calls.append(result.call)
        outputs.append(
            result.output.model_copy(
                update={
                    "notable_points": supported_points(result.output.notable_points, text.pages)
                }
            )
        )
    return outputs, calls


async def consolidate_summaries(
    summaries: list[DocumentSummary],
    *,
    flagged_documents: list[str],
    excluded_files: list[str],
    llm: LLMProvider,
    prompts: SystemPromptCatalog,
    delay_seconds: float,
) -> tuple[ConsolidatedReport, list[LLMCall]]:
    await asyncio.sleep(delay_seconds)
    marked = [datamark_values(item.model_dump(mode="json")) for item in summaries]
    request = prompts.get("consolidation").for_call(
        {
            "summaries": json.dumps(marked),
            "flagged": json.dumps(flagged_documents),
            "excluded": json.dumps(excluded_files),
        }
    )
    result = await llm.complete(request, ConsolidatedReport)
    report = result.output.model_copy(
        update={
            "sections": [
                _verified_for_report(section, summaries) for section in result.output.sections
            ]
        }
    )
    return report, [result.call]


def _verified_section(section: Section, pages: Sequence[PageText], filename: str) -> Section:
    """Keep only pull quotes that appear on the page they cite."""
    quotes = [
        quote.model_copy(update={"quote": _plain(quote.quote), "document": filename})
        for quote in section.quotes
    ]
    points = [NotablePoint(text=q.quote, page=q.page, quote=q.quote) for q in quotes]
    kept = {(point.page, point.quote) for point in supported_points(points, pages)}
    return section.model_copy(update={"quotes": [q for q in quotes if (q.page, q.quote) in kept]})


def _verified_for_report(section: Section, summaries: Sequence[DocumentSummary]) -> Section:
    """Keep only pull quotes that a document summary already holds as a verified quote."""
    known = {
        (point.page, _plain(point.quote))
        for summary in summaries
        for point in summary.notable_points
    }
    quotes = [
        quote.model_copy(update={"quote": _plain(quote.quote)})
        for quote in section.quotes
        if (quote.page, _plain(quote.quote)) in known
    ]
    return section.model_copy(update={"quotes": quotes})


def _plain(value: str) -> str:
    """Collapse whitespace and drop the ^ marks that datamarking puts between words."""
    return " ".join(word for word in value.split() if word != "^")


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
