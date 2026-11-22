"""Add the text that sits in pictures to the text a PDF already gives us.

Extraction marks a page `needs_image` when it shows a picture. This step looks at those pages
through a `PageReader` and appends what it finds to the page text. After that, chunking,
the safety check, summaries, and quote checks work on the page as before.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.ports import LLMCall, PageReader
from app.pipeline.datamark import datamark
from app.pipeline.images import render_image_pages
from app.pipeline.models import ExtractedText, PageText
from app.pipeline.prompts import SystemPromptCatalog

logger = logging.getLogger("app.vision")

PROMPT_ID = "page_image"
_NOTHING = "NONE"
_LABEL = "Text and figures in the images on this page:"


@dataclass(frozen=True)
class VisionLimits:
    dpi: int = 110
    min_image_fraction: float = 0.05
    max_pages: int = 16
    concurrency: int = 4


async def read_image_pages(
    text: ExtractedText,
    data: bytes,
    reader: PageReader,
    prompts: SystemPromptCatalog,
    *,
    filename: str,
    limits: VisionLimits | None = None,
) -> tuple[ExtractedText, list[LLMCall]]:
    """The same pages, with image text added to those that show pictures.

    A failure from the reader is not caught. The worker retries the step, so a page with a
    chart is never summarised as if the chart were not there.
    """
    chosen = limits or VisionLimits()
    candidates = _candidates(text.pages)
    if not candidates:
        return text, []
    images = await asyncio.to_thread(
        render_image_pages,
        data,
        [page.page for page in candidates],
        dpi=chosen.dpi,
        min_image_fraction=chosen.min_image_fraction,
    )
    queue = [page for page in candidates if page.page in images]
    chosen_pages = queue[: chosen.max_pages]
    if len(queue) > len(chosen_pages):
        logger.warning(
            "%s: reading %s of %s image pages, the rest are left unread",
            filename,
            len(chosen_pages),
            len(queue),
        )
    if not chosen_pages:
        return text, []
    prompt = prompts.get(PROMPT_ID)
    gate = asyncio.Semaphore(chosen.concurrency)

    async def one(page: PageText) -> tuple[int, str, LLMCall]:
        request = prompt.for_call(
            {
                "filename": filename,
                "page": str(page.page),
                "page_text": datamark(page.text),
            }
        )
        async with gate:
            reading = await reader.read(request, images[page.page])
        return page.page, _clean(reading.text), reading.call

    tasks = [asyncio.create_task(one(page)) for page in chosen_pages]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        raise
    found = {number: words for number, words, _call in results}
    pages = [_merged(page, found.get(page.page, "")) for page in text.pages]
    return ExtractedText(pages=pages), [call for _number, _words, call in results]


def _candidates(pages: Sequence[PageText]) -> list[PageText]:
    """Pages that show a picture. Scans with no text come first: they are all picture."""
    marked = [page for page in pages if page.needs_image]
    return sorted(marked, key=lambda page: (bool(page.text.strip()), page.page))


def _clean(value: str) -> str:
    words = value.strip()
    return "" if words.upper().rstrip(".") == _NOTHING else words


def _merged(page: PageText, found: str) -> PageText:
    if not found:
        return page
    if not page.text.strip():
        return page.model_copy(update={"text": found})
    return page.model_copy(update={"text": f"{page.text}\n\n{_LABEL}\n{found}"})
