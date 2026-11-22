from collections.abc import Sequence

from app.pipeline.models import NotablePoint, PageText


def supported_points(
    points: Sequence[NotablePoint],
    pages: Sequence[PageText],
) -> list[NotablePoint]:
    text = {page.page: _words(page.text) for page in pages}
    return [point for point in points if _words(point.quote) in text.get(point.page, "")]


def _words(value: str) -> str:
    return " ".join(value.split())
