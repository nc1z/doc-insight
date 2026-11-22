import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from app.domain.failures import StepFailure
from app.pipeline.models import ExtractInput, PageText
from app.pipeline.steps import extract_text

_SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def test_extract_reads_each_page_of_a_digital_memo() -> None:
    pages = asyncio.run(_pages("desk-note.pdf"))

    assert len(pages) == 1
    assert pages[0].needs_image is False
    assert "Cedar Ridge Capital" in pages[0].text
    assert "NTLN" in pages[0].text


def test_extract_keeps_every_page_of_a_longer_memo() -> None:
    pages = asyncio.run(_pages("company-primer.pdf"))

    assert [page.page for page in pages] == [1, 2, 3]
    assert all(page.text and not page.needs_image for page in pages)


def test_extract_marks_a_scanned_page_for_image_handling() -> None:
    pages = asyncio.run(_pages("expert-call.pdf"))

    assert len(pages) == 1
    assert pages[0].text == ""
    assert pages[0].needs_image is True


def test_extract_reads_two_full_pages_and_marks_the_infographic() -> None:
    pages = asyncio.run(_pages("coverage-memo.pdf"))

    assert [page.page for page in pages] == [1, 2, 3]
    assert len(pages[0].text) > 2500
    assert len(pages[1].text) > 2500
    assert pages[0].needs_image is False
    assert pages[1].needs_image is False
    assert "figure" in pages[2].text.lower()
    assert pages[2].needs_image is True


def test_extract_marks_only_the_chart_page() -> None:
    pages = asyncio.run(_pages("terminal-snapshot.pdf"))

    assert [page.page for page in pages] == [1, 2]
    assert "Short interest" in pages[0].text
    assert pages[0].needs_image is False
    assert pages[1].text == ""
    assert pages[1].needs_image is True


def test_extract_leaves_a_short_text_page_unmarked() -> None:
    extracted = asyncio.run(
        extract_text(
            ExtractInput(filename="short.pdf", page_count=1),
            _short_note(),
            delay_seconds=0,
        )
    )

    assert len(extracted.pages) == 1
    assert "See you Monday." in extracted.pages[0].text
    assert extracted.pages[0].needs_image is False


def test_extract_rejects_bytes_that_are_not_a_pdf() -> None:
    with pytest.raises(StepFailure) as caught:
        asyncio.run(
            extract_text(
                ExtractInput(filename="broken.pdf", page_count=None),
                b"not-a-pdf",
                delay_seconds=0,
            )
        )

    assert caught.value.code == "unreadable_document"
    assert caught.value.permanent is True


def _short_note() -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.drawString(72, 720, "See you Monday.")
    pdf.save()
    return buffer.getvalue()


async def _pages(filename: str) -> list[PageText]:
    extracted = await extract_text(
        ExtractInput(filename=filename, page_count=None),
        (_SAMPLES / filename).read_bytes(),
        delay_seconds=0,
    )
    return extracted.pages
