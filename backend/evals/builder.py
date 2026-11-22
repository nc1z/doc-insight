"""Render the eval PDFs described by fixtures.json.

The generated files are disposable. Tests build them in memory, and
`python -m evals.builder` writes them under backend/evals/generated/.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.actions import JavaScript
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FIXTURES_PATH = Path(__file__).with_name("fixtures.json")
_FONT_PATH = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"
_FONT = "DejaVu"
_MARGIN = 54
_BODY_SIZE = 11

pdfmetrics.registerFont(TTFont(_FONT, str(_FONT_PATH)))


@dataclass(frozen=True)
class BuiltFile:
    filename: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class FixtureLimits:
    max_file_bytes: int
    max_page_count: int
    max_file_count: int


def load_fixtures(path: Path = _FIXTURES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def build_fixture(
    name: str,
    limits: FixtureLimits,
    fixtures: Mapping[str, Any] | None = None,
) -> BuiltFile:
    catalog = dict(fixtures) if fixtures is not None else load_fixtures()
    if name in catalog["binary_fixtures"]:
        return _build_binary(catalog["binary_fixtures"][name], catalog, limits)
    if name in catalog["documents"]:
        document = _resolve_document(name, catalog["documents"])
        return BuiltFile(document["filename"], render_pages(document["pages"]), "application/pdf")
    raise KeyError(f"Unknown fixture: {name}")


def build_upload(
    files: Sequence[Any] | Mapping[str, Any],
    limits: FixtureLimits,
    fixtures: Mapping[str, Any] | None = None,
) -> list[BuiltFile]:
    catalog = dict(fixtures) if fixtures is not None else load_fixtures()
    items = files if isinstance(files, list) else [files]
    built: list[BuiltFile] = []
    for item in items:
        if isinstance(item, str):
            built.append(build_fixture(item, limits, catalog))
            continue
        count = _quantity(item.get("count", 1), limits.max_file_count)
        file = build_fixture(str(item["fixture"]), limits, catalog)
        filename = str(item.get("filename", file.filename))
        built.extend(BuiltFile(filename, file.data, file.content_type) for _ in range(count))
    return built


def render_pages(pages: Sequence[Mapping[str, Any]]) -> bytes:
    writer = PdfWriter()
    for page in pages:
        writer.append(BytesIO(_render_page(page)))
    for index, page in enumerate(pages):
        if invisible := page.get("invisible_text"):
            _stamp_tag_text(writer, index, str(invisible))
    return _save(writer)


def write_generated(directory: Path, limits: FixtureLimits | None = None) -> None:
    chosen = limits or FixtureLimits(20 * 1024 * 1024, 100, 10)
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = load_fixtures()
    names = [*fixtures["documents"], *fixtures["binary_fixtures"]]
    for name in names:
        built = build_fixture(name, chosen, fixtures)
        (directory / built.filename).write_bytes(built.data)


def _resolve_document(name: str, documents: Mapping[str, Any]) -> dict[str, Any]:
    spec = documents[name]
    if "extends" in spec:
        base = _resolve_document(str(spec["extends"]), documents)
        pages = [*base["pages"], *spec.get("append_pages", [])]
        return {"filename": spec["filename"], "pages": pages}
    if "pages_by_number" in spec:
        template = str(spec["filler"]["text"])
        numbered = spec["pages_by_number"]
        pages = []
        for number in range(1, int(spec["total_pages"]) + 1):
            page = numbered.get(str(number))
            pages.append(page if page is not None else {"text": template.format(page=number)})
        return {"filename": spec["filename"], "pages": pages}
    return {"filename": spec["filename"], "pages": list(spec["pages"])}


def _render_page(page: Mapping[str, Any]) -> bytes:
    if "chart" in page:
        return _image_pdf(_chart_png(page["chart"]))
    if page.get("render") == "scanned":
        return _image_pdf(_scanned_png(str(page.get("text", ""))))
    return _text_pdf(_visible_text(page), page.get("hidden_text"))


def _visible_text(page: Mapping[str, Any]) -> str:
    if "repeat" in page:
        item = page["repeat"]
        return str(item["text"]) * int(item["times"])
    return str(page.get("text", ""))


def _text_pdf(text: str, hidden: Any) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFillColor(colors.black)
    pdf.setFont(_FONT, _BODY_SIZE)
    if len(text) > 4000:
        pdf.drawString(_MARGIN, 720, text)
    else:
        y = 740.0
        for line in _wrap(text, _BODY_SIZE, letter[0] - (2 * _MARGIN)):
            pdf.drawString(_MARGIN, y, line)
            y -= 15
    if hidden:
        pdf.setFillColor(colors.white)
        pdf.setFont(_FONT, 1)
        pdf.drawString(_MARGIN, 36, str(hidden))
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _image_pdf(png: bytes) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawImage(
        ImageReader(BytesIO(png)),
        0,
        0,
        width=letter[0],
        height=letter[1],
        preserveAspectRatio=True,
        anchor="c",
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _chart_png(chart: Mapping[str, Any]) -> bytes:
    image = Image.new("RGB", (1200, 1500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_FONT_PATH, 36)
    draw.text((80, 80), str(chart.get("title", "")), fill="black", font=font)
    bars = list(chart["bars"])
    peak = max(int(bar["value"]) for bar in bars) or 1
    base = 1200
    for index, bar in enumerate(bars):
        left = 150 + index * 220
        height = int(800 * int(bar["value"]) / peak)
        draw.rectangle((left, base - height, left + 120, base), fill="#1f4e79")
        draw.text((left, base + 30), str(bar["label"]), fill="black", font=font)
        draw.text((left, base - height - 50), str(bar["value"]), fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _scanned_png(text: str) -> bytes:
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_FONT_PATH, 32)
    y = 80
    for line in _wrap_pixels(text, font, 1040):
        draw.text((80, y), line, fill="black", font=font)
        y += 48
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _wrap(text: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            if not word:
                continue
            trial = word if not current else f"{current} {word}"
            if pdfmetrics.stringWidth(trial, _FONT, size) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _wrap_pixels(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            if not word:
                continue
            trial = word if not current else f"{current} {word}"
            if font.getlength(trial) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _stamp_tag_text(writer: PdfWriter, page_index: int, text: str) -> None:
    """Append Unicode tag characters. Text rendering mode 3 keeps them invisible."""
    if any(ord(char) > 127 for char in text):
        raise ValueError("Invisible fixture text must be ASCII")
    page = writer.pages[page_index]
    codes = bytearray()
    entries: list[str] = []
    for index, char in enumerate(text, start=1):
        codepoint = 0xE0000 + ord(char)
        value = codepoint - 0x10000
        high = 0xD800 + (value >> 10)
        low = 0xDC00 + (value & 0x3FF)
        entries.append(f"<{index:02X}> <{high:04X}{low:04X}>")
        codes.append(index)
    cmap = "\n".join(
        [
            "/CIDInit /ProcSet findresource begin",
            "12 dict begin",
            "begincmap",
            "/CMapName /TagCMap def",
            "/CMapType 2 def",
            "1 begincodespacerange",
            "<00> <FF>",
            "endcodespacerange",
            f"{len(entries)} beginbfchar",
            *entries,
            "endbfchar",
            "endcmap",
            "CMapName currentdict /CMap defineresource pop",
            "end",
            "end",
        ]
    )
    mapping = DecodedStreamObject()
    mapping.set_data(cmap.encode("latin1"))
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/ToUnicode"): writer._add_object(mapping),
        }
    )
    fonts = page["/Resources"]["/Font"]
    fonts[NameObject("/TagFont")] = writer._add_object(font)
    stream = DecodedStreamObject()
    stream.set_data(f"BT /TagFont 1 Tf 3 Tr 50 20 Tm <{codes.hex()}> Tj ET".encode())
    extra = writer._add_object(stream)
    contents = page["/Contents"]
    if isinstance(contents, ArrayObject):
        contents.append(extra)
    else:
        page[NameObject("/Contents")] = ArrayObject([contents, extra])


def _build_binary(
    spec: Mapping[str, Any],
    fixtures: Mapping[str, Any],
    limits: FixtureLimits,
) -> BuiltFile:
    filename = str(spec["filename"])
    if spec["build"] == "plain_text":
        return BuiltFile(filename, str(spec["content"]).encode(), "text/plain")
    source = build_fixture(str(spec["source"]), limits, fixtures).data
    kind = str(spec["build"])
    if kind == "truncate":
        kept = max(1, int(len(source) * float(spec["keep_fraction"])))
        data = source[:kept]
    elif kind == "encrypt":
        data = _encrypt(source, str(spec["user_password"]))
    elif kind == "add_javascript":
        data = _javascript(source, str(spec["script"]))
    elif kind == "add_attachment":
        data = _attachment(source, str(spec["attachment_name"]))
    elif kind == "pad_to_size":
        target = _quantity(spec["size"], limits.max_file_bytes)
        data = source if len(source) >= target else source + b"\n" * (target - len(source))
    elif kind == "repeat_pages":
        data = _repeat_pages(source, _quantity(spec["pages"], limits.max_page_count))
    else:
        raise ValueError(f"Unknown fixture build: {kind}")
    return BuiltFile(filename, data, "application/pdf")


def _encrypt(data: bytes, password: str) -> bytes:
    writer = _copy(data)
    writer.encrypt(user_password=password)
    return _save(writer)


def _javascript(data: bytes, script: str) -> bytes:
    writer = _copy(data)
    writer.add_open_action(JavaScript(script))
    return _save(writer)


def _attachment(data: bytes, name: str) -> bytes:
    writer = _copy(data)
    writer.add_attachment(name, b"sample attachment")
    return _save(writer)


def _repeat_pages(data: bytes, count: int) -> bytes:
    reader = PdfReader(BytesIO(data))
    writer = PdfWriter()
    while len(writer.pages) < count:
        for page in reader.pages:
            if len(writer.pages) >= count:
                break
            writer.add_page(page)
    return _save(writer)


def _copy(data: bytes) -> PdfWriter:
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(data)))
    return writer


def _save(writer: PdfWriter) -> bytes:
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _quantity(value: int | str, limit: int) -> int:
    if value == "limit_plus_1":
        return limit + 1
    if value == "limit_plus_1_mb":
        return limit + 1024 * 1024
    if isinstance(value, int):
        return value
    raise ValueError(f"Unknown fixture quantity: {value}")


def main() -> None:
    write_generated(Path(__file__).with_name("generated"))


if __name__ == "__main__":
    main()
