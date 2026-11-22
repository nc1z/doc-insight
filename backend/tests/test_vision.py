import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.adapters.mocks.mock_vision import MOCK_IMAGE_TEXT, MockPageReader
from app.core.config import Settings
from app.domain.ports import LLMCall, LLMRequest, PageReading
from app.pipeline.models import ExtractedText, ExtractInput
from app.pipeline.prompts import SystemPromptCatalog, load_system_prompts
from app.pipeline.steps import extract_text
from app.pipeline.vision import VisionLimits, read_image_pages
from evals.builder import render_pages

_PNG = b"\x89PNG\r\n\x1a\n"
_CHART = {
    "infographic": {
        "title": "Spend by lab",
        "note": "Share of spend.",
        "parts": [{"label": "A", "share": 0.6, "value": "60%"}],
    }
}


class _Reader:
    """Answers from a script and keeps what it was asked."""

    def __init__(self, answers: dict[int, str] | None = None, *, delay: float = 0) -> None:
        self.answers = answers or {}
        self.delay = delay
        self.requests: list[LLMRequest] = []
        self.images: list[bytes] = []
        self.running = 0
        self.peak = 0

    async def read(self, request: LLMRequest, image: bytes) -> PageReading:
        self.requests.append(request)
        self.images.append(image)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.running -= 1
        page = int(request.user.split("page: ")[1].split("\n")[0])
        text = self.answers.get(page, "Found in the image.")
        return PageReading(text=text, call=LLMCall("fake", "page_image", 1, 3, 4, 5))


class _Broken:
    async def read(self, request: LLMRequest, image: bytes) -> PageReading:
        raise RuntimeError("model unavailable")


def _prompts() -> SystemPromptCatalog:
    return load_system_prompts(Settings(_env_file=None).system_prompts_path)


def _extracted(pdf: bytes) -> ExtractedText:
    return asyncio.run(
        extract_text(ExtractInput(filename="doc.pdf", page_count=None), pdf, delay_seconds=0)
    )


def _read(
    pdf: bytes,
    reader: object,
    limits: VisionLimits | None = None,
) -> tuple[ExtractedText, list[LLMCall]]:
    return asyncio.run(
        read_image_pages(
            _extracted(pdf),
            pdf,
            reader,  # type: ignore[arg-type]
            _prompts(),
            filename="doc.pdf",
            limits=limits,
        )
    )


def _mixed_pdf() -> bytes:
    return render_pages(
        [
            {"text": "Page one is plain text."},
            {"text": "The figure below has the numbers.", **_CHART},
            {"render": "scanned", "text": "A scanned note about lead times."},
        ]
    )


def test_pages_with_pictures_are_read_and_the_rest_are_left_alone() -> None:
    reader = _Reader({2: "Spend by lab\nA: 60%", 3: "A scanned note about lead times."})

    result, calls = _read(_mixed_pdf(), reader)

    first, second, third = result.pages
    assert first.text.startswith("Page one")
    assert "Found" not in first.text
    assert second.text.startswith("The figure below has the numbers.")
    assert "Text and figures in the images on this page:\nSpend by lab\nA: 60%" in second.text
    assert third.text == "A scanned note about lead times."
    assert [page.page for page in result.pages] == [1, 2, 3]
    assert len(reader.images) == 2
    assert all(image.startswith(_PNG) for image in reader.images)
    assert [call.model for call in calls] == ["fake", "fake"]


def test_the_request_names_the_file_and_page_and_marks_the_page_text() -> None:
    reader = _Reader()

    _read(_mixed_pdf(), reader)

    by_page = {int(r.user.split("page: ")[1].split("\n")[0]): r for r in reader.requests}
    scan, chart = by_page[3], by_page[2]
    assert "filename: doc.pdf" in chart.user
    assert "page_text: The^figure^below^has^the^numbers." in chart.user
    assert scan.user.endswith("page_text: ")
    assert chart.prompt_id == "page_image"
    assert "CANARY-7F3A9C" in chart.system


def test_a_page_with_nothing_new_keeps_its_text() -> None:
    result, _calls = _read(_mixed_pdf(), _Reader({2: "NONE", 3: "none."}))

    assert result.pages[1].text == "The figure below has the numbers."
    assert result.pages[2].text == ""


def test_a_logo_is_not_worth_a_model_call() -> None:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 700, "A page of text with a small logo.")
    logo = BytesIO()
    Image.new("RGB", (40, 40), "navy").save(logo, format="PNG")
    pdf.drawImage(ImageReader(logo), 72, 740, width=40, height=40)
    pdf.showPage()
    pdf.save()
    reader = _Reader()

    result, calls = _read(buffer.getvalue(), reader)

    assert result.pages[0].needs_image is True
    assert reader.requests == []
    assert calls == []


def test_a_document_with_no_pictures_never_reaches_the_reader() -> None:
    reader = _Reader()

    result, calls = _read(render_pages([{"text": "Only words here."}]), reader)

    assert result.pages[0].text.startswith("Only words")
    assert reader.requests == []
    assert calls == []


def test_the_page_cap_reads_scans_first() -> None:
    pdf = render_pages(
        [
            {"text": "Text with a figure.", **_CHART},
            {"render": "scanned", "text": "First scan."},
            {"render": "scanned", "text": "Second scan."},
        ]
    )
    reader = _Reader()

    result, calls = _read(pdf, reader, VisionLimits(max_pages=2))

    assert len(calls) == 2
    assert result.pages[0].text == "Text with a figure."
    assert result.pages[1].text == "Found in the image."
    assert result.pages[2].text == "Found in the image."


def test_pages_are_read_at_the_same_time_up_to_the_limit() -> None:
    pdf = render_pages([{"render": "scanned", "text": f"Scan {n}."} for n in range(1, 7)])
    reader = _Reader(delay=0.05)

    _read(pdf, reader, VisionLimits(concurrency=2))

    assert reader.peak == 2


def test_a_reader_failure_is_not_swallowed() -> None:
    with pytest.raises(RuntimeError, match="model unavailable"):
        _read(_mixed_pdf(), _Broken())


def test_the_mock_reader_adds_one_fixed_line() -> None:
    result, calls = _read(_mixed_pdf(), MockPageReader())

    assert result.pages[2].text == MOCK_IMAGE_TEXT
    assert result.pages[1].text.endswith(MOCK_IMAGE_TEXT)
    assert [call.model for call in calls] == ["mock-vision", "mock-vision"]


def test_the_page_image_prompt_is_in_the_catalog() -> None:
    prompt = _prompts().get("page_image")

    assert prompt.version == 1
    assert prompt.placeholders == ("filename", "page", "page_text")
    assert prompt.system is not None
    assert "CANARY-7F3A9C" in prompt.system


def test_a_catalog_without_the_page_image_prompt_still_loads(tmp_path: Path) -> None:
    source = Settings(_env_file=None).system_prompts_path.read_text(encoding="utf-8")
    trimmed = source.split("- id: page_image")[0]
    path = tmp_path / "prompts.yaml"
    path.write_text(trimmed, encoding="utf-8")

    catalog = load_system_prompts(path)

    with pytest.raises(ValueError, match="Unknown system prompt: page_image"):
        catalog.get("page_image")
