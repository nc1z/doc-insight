"""Per-page text from a PDF. A page that displays an image is marked for Phase 11."""

from typing import Any

import pymupdf
import pymupdf4llm

from app.domain.failures import StepFailure
from app.pipeline.models import PageText


def extract_pdf_pages(data: bytes) -> list[PageText]:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise StepFailure("unreadable_document", permanent=True) from exc
    try:
        image_pages = _image_pages(document)
        chunks = pymupdf4llm.to_markdown(document, page_chunks=True)
    except Exception as exc:
        raise StepFailure("unreadable_document", permanent=True) from exc
    finally:
        document.close()
    if not isinstance(chunks, list):
        raise StepFailure("unreadable_document", permanent=True)
    pages: list[PageText] = []
    for chunk in chunks:
        page = _page(chunk, image_pages)
        if page is not None:
            pages.append(page)
    if not pages:
        raise StepFailure("unreadable_document", permanent=True)
    return pages


def _image_pages(document: Any) -> set[int]:
    """Pages that display an image. get_image_info is the list of those images."""
    return {index + 1 for index in range(document.page_count) if document[index].get_image_info()}


def _page(chunk: object, image_pages: set[int]) -> PageText | None:
    if not isinstance(chunk, dict):
        return None
    metadata = chunk.get("metadata")
    number = metadata.get("page_number") if isinstance(metadata, dict) else None
    if not isinstance(number, int):
        return None
    raw = chunk.get("text")
    text = raw.strip() if isinstance(raw, str) else ""
    return PageText(page=number, text=text, needs_image=number in image_pages)
