import asyncio
from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.pipeline.chunk import chunk_pages, count_tokens
from app.pipeline.models import ExtractInput, PageText
from app.pipeline.steps import extract_text

_SAMPLES = Path(__file__).resolve().parents[2] / "samples"
_BUDGET = Settings(_env_file=None, classifier_provider="mock").chunk_token_budget


def test_a_short_page_is_one_chunk() -> None:
    chunks = chunk_pages([PageText(page=2, text="See you Monday.")], _BUDGET)

    assert [(chunk.page, chunk.text) for chunk in chunks] == [(2, "See you Monday.")]
    assert chunks[0].token_count <= _BUDGET


def test_a_blank_page_has_no_chunk() -> None:
    assert chunk_pages([PageText(page=1, text="   ")], _BUDGET) == []


def test_each_page_keeps_its_own_chunks() -> None:
    chunks = chunk_pages(
        [PageText(page=1, text="Alpha."), PageText(page=4, text="Beta.")],
        token_budget=100,
    )

    assert [(chunk.page, chunk.text) for chunk in chunks] == [(1, "Alpha."), (4, "Beta.")]


def test_a_page_splits_inside_the_budget_and_keeps_its_page_number() -> None:
    text = "Alpha sentence here.\n\nBeta sentence here."
    budget = count_tokens("Alpha sentence here.")
    chunks = chunk_pages([PageText(page=3, text=text)], budget)

    assert [chunk.page for chunk in chunks] == [3, 3]
    assert all(chunk.token_count <= budget for chunk in chunks)
    assert "Alpha sentence here." in chunks[0].text
    assert "Beta sentence here." in chunks[1].text


def test_sample_chunks_carry_the_page_number() -> None:
    pages = asyncio.run(_pages("company-primer.pdf"))
    chunks = chunk_pages(pages, _BUDGET)

    assert [chunk.page for chunk in chunks] == [1, 2, 3]
    assert all(chunk.text and chunk.token_count <= _BUDGET for chunk in chunks)
    assert "Northline" in chunks[0].text


def test_a_full_page_of_text_is_one_chunk() -> None:
    pages = asyncio.run(_extracted(_full_page()))
    chunks = chunk_pages(pages, _BUDGET)

    assert [chunk.page for chunk in chunks] == [1]
    assert chunks[0].token_count > 1000
    assert chunks[0].token_count <= _BUDGET


def test_an_empty_chart_page_is_not_a_chunk() -> None:
    pages = asyncio.run(_pages("terminal-snapshot.pdf"))
    chunks = chunk_pages(pages, _BUDGET)

    assert [chunk.page for chunk in chunks] == [1]
    assert "Short interest" in chunks[0].text


async def _pages(filename: str) -> list[PageText]:
    return await _extracted((_SAMPLES / filename).read_bytes())


async def _extracted(data: bytes) -> list[PageText]:
    extracted = await extract_text(
        ExtractInput(filename="page.pdf", page_count=None),
        data,
        delay_seconds=0,
    )
    return extracted.pages


def _full_page() -> bytes:
    """A letter page set tight: 8pt text from margin to margin."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    pdf.setFont("Times-Roman", 8)
    margin = 36
    y = 792 - margin
    line = ""
    while y >= margin:
        line = ""
        while pdf.stringWidth(f"{line} market", "Times-Roman", 8) <= 612 - 2 * margin:
            line += " market"
        pdf.drawString(margin, y, line.strip())
        y -= 10
    pdf.save()
    return buffer.getvalue()
