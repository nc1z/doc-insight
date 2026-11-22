"""Turn the pages of a PDF that show pictures into PNG images a reader can look at."""

from collections.abc import Sequence

import pymupdf

# A long side above this is scaled down. A poster-sized page stays a sensible request.
_MAX_SIDE_PIXELS = 2000


def render_image_pages(
    data: bytes,
    pages: Sequence[int],
    *,
    dpi: int,
    min_image_fraction: float,
) -> dict[int, bytes]:
    """PNG for each listed page (1-based) whose pictures cover enough of it.

    A page whose pictures are only a logo or an icon is left out, so it costs no model call.
    """
    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        rendered: dict[int, bytes] = {}
        for number in pages:
            if not 1 <= number <= document.page_count:
                continue
            page = document[number - 1]
            if _image_fraction(page) < min_image_fraction:
                continue
            rendered[number] = _png(page, dpi)
        return rendered
    finally:
        document.close()


def _image_fraction(page: pymupdf.Page) -> float:
    area = page.rect.width * page.rect.height
    if area <= 0:
        return 0.0
    covered = 0.0
    for info in page.get_image_info():
        box = pymupdf.Rect(info["bbox"]) & page.rect
        if not box.is_empty:
            covered += box.width * box.height
    return min(covered / area, 1.0)


def _png(page: pymupdf.Page, dpi: int) -> bytes:
    zoom = dpi / 72
    longest = max(page.rect.width, page.rect.height) * zoom
    if longest > _MAX_SIDE_PIXELS:
        zoom *= _MAX_SIDE_PIXELS / longest
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return bytes(pixmap.tobytes("png"))
