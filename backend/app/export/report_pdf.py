"""Render a finished job as a PDF: one overview page, then one page per document."""

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

import pymupdf

from app.domain.models import Document, Job

_PAGE = pymupdf.paper_rect("a4")
_MARGIN = 54
_FOOTER = 28
_MIN_SCALE = 0.3
_HEADLINE_WORDS = 14

_CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.4; color: #1c1c21; }
.eyebrow { font-size: 9.5pt; color: #6b6b76; margin: 0 0 6pt 0; }
h1 { font-size: 24pt; line-height: 1.12; font-weight: bold; margin: 0 0 14pt 0; }
h2 { font-size: 8.5pt; color: #6b6b76; text-transform: uppercase; margin: 18pt 0 6pt 0; }
h3 { font-size: 12pt; margin: 12pt 0 4pt 0; }
p { margin: 0 0 6pt 0; }
ol { margin: 0 0 4pt 0; padding: 0; }
li { margin: 0 0 5pt 0; }
.num { color: #8a8a94; }
.quote { margin: 4pt 0 8pt 8pt; padding-left: 8pt; border-left: 2pt solid #c9c9d1;
         font-style: italic; color: #4a4a54; }
.source { font-size: 8.5pt; color: #6b6b76; margin: -4pt 0 8pt 16pt; }
.tags { color: #4a4a54; }
.meta { font-size: 9.5pt; }
.muted { color: #6b6b76; }
"""


def render_report_pdf(job: Job) -> bytes:
    """Page 1 is the overview. Page 2 onwards are the documents, in the order the UI shows them."""
    documents = _documents(job)
    pages = [_overview(job.report, documents)] + [_document(item) for item in documents]
    pdf = pymupdf.open()
    try:
        for number, html in enumerate(pages, start=1):
            page = pdf.new_page(width=_PAGE.width, height=_PAGE.height)
            body = pymupdf.Rect(
                _MARGIN, _MARGIN, _PAGE.width - _MARGIN, _PAGE.height - _MARGIN - _FOOTER
            )
            page.insert_htmlbox(body, html, css=_CSS, scale_low=_MIN_SCALE)
            page.insert_text(
                (_MARGIN, _PAGE.height - _MARGIN),
                f"Doc Insight - page {number} of {len(pages)}",
                fontsize=8,
                color=(0.55, 0.55, 0.6),
            )
        return pdf.tobytes(deflate=True)
    finally:
        pdf.close()


def _documents(job: Job) -> list[Document]:
    ordered = sorted(job.documents, key=lambda item: (item.created_at, item.filename))
    return [item for item in ordered if item.storage_key is not None and not item.excluded]


def _overview(report: Mapping[str, Any] | None, documents: Sequence[Document]) -> str:
    if not report:
        return _heading("Overview", "The report is not ready.")
    headline, intro = _split_headline(_text(report.get("summary")))
    points = _strings(report.get("takeaways"))[:5]
    sections = _sections(report.get("sections"), intro)
    parts = [_heading("Overview", headline), _points(points)]
    parts.append(_reading(sections))
    disagreements = _contradictions(report.get("contradictions"))
    if disagreements:
        parts.append(f"<h2>Where the documents disagree</h2>{disagreements}")
    themes = _strings(report.get("themes"))
    if themes:
        parts.append(f"<h2>Themes</h2><p class='tags'>{_join(themes)}</p>")
    entities = report.get("entities")
    rows = [
        ("Documents", [item.filename for item in documents]),
        *_entity_rows(entities),
        ("Flagged", _strings(report.get("flagged_documents"))),
        ("Left out", _strings(report.get("excluded_files"))),
    ]
    parts.append(_metadata(rows))
    return "".join(parts)


def _document(document: Document) -> str:
    summary = document.summary
    if not summary:
        return _heading(document.filename, "This file has no summary yet.")
    headline, intro = _split_headline(_text(summary.get("summary")))
    title = _text(summary.get("title")) or document.filename
    kind = _text(summary.get("inferred_type")).replace("_", " ").capitalize()
    eyebrow = " · ".join(part for part in (title, kind) if part)
    parts = [_heading(eyebrow, headline), _points(_strings(summary.get("key_points"))[:3])]
    parts.append(_reading(_sections(summary.get("sections"), intro)))
    topics = _strings(summary.get("topics"))
    if topics:
        parts.append(f"<h2>Topics</h2><p class='tags'>{_join(topics)}</p>")
    rows = [
        ("Type", [kind] if kind else []),
        ("File", [document.filename]),
        *_entity_rows(summary.get("entities")),
    ]
    parts.append(_metadata(rows))
    return "".join(parts)


def _heading(eyebrow: str, headline: str) -> str:
    return f"<p class='eyebrow'>{escape(eyebrow)}</p><h1>{escape(headline)}</h1>"


def _points(points: Sequence[str]) -> str:
    if not points:
        return ""
    items = "".join(
        f"<li><span class='num'>{index:02d}</span>&nbsp;&nbsp;{escape(point)}</li>"
        for index, point in enumerate(points, start=1)
    )
    return f"<ol style='list-style-type: none'>{items}</ol>"


def _reading(sections: Sequence[Mapping[str, Any]]) -> str:
    if not sections:
        return ""
    blocks = ["<h2>Further reading</h2>"]
    for section in sections:
        heading = _text(section.get("heading"))
        if heading:
            blocks.append(f"<h3>{escape(heading)}</h3>")
        paragraphs = _strings(section.get("paragraphs"))
        quotes = [item for item in _list(section.get("quotes")) if isinstance(item, Mapping)]
        blocks.extend(_interleave(paragraphs, quotes))
    return "".join(blocks)


def _interleave(paragraphs: Sequence[str], quotes: Sequence[Mapping[str, Any]]) -> list[str]:
    """Quotes sit between paragraphs, spread evenly, like the page in the UI."""
    after: dict[int, list[Mapping[str, Any]]] = {}
    for index, quote in enumerate(quotes):
        at = max(0, ((index + 1) * len(paragraphs)) // (len(quotes) + 1) - 1)
        after.setdefault(at, []).append(quote)
    blocks: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        blocks.append(f"<p>{escape(paragraph)}</p>")
        blocks.extend(_quote(item) for item in after.get(index, []))
    return blocks


def _quote(quote: Mapping[str, Any]) -> str:
    words = _text(quote.get("quote"))
    if not words:
        return ""
    source = _source(_text(quote.get("document")), quote.get("page"))
    return f"<p class='quote'>“{escape(words)}”</p><p class='source'>{escape(source)}</p>"


def _contradictions(value: object) -> str:
    blocks: list[str] = []
    for item in _list(value):
        if not isinstance(item, Mapping):
            continue
        blocks.append(f"<h3>{escape(_text(item.get('about')))}</h3>")
        for claim in _list(item.get("claims")):
            if isinstance(claim, Mapping):
                blocks.append(f"<p>{escape(_text(claim.get('text')))}</p>{_quote(claim)}")
    return "".join(blocks)


def _metadata(rows: Sequence[tuple[str, Sequence[str]]]) -> str:
    items = "".join(
        f"<li><span class='muted'>{escape(label)}:</span> {_join(values)}</li>"
        for label, values in rows
        if values
    )
    if not items:
        return ""
    return f"<h2>Metadata</h2><ul class='meta'>{items}</ul>"


def _entity_rows(value: object) -> list[tuple[str, list[str]]]:
    entities = value if isinstance(value, Mapping) else {}
    labels = (
        ("people", "People"),
        ("organisations", "Organisations"),
        ("locations", "Locations"),
        ("dates", "Dates"),
    )
    return [
        (label, [_text(item.get("name")) for item in _list(entities.get(key)) if _named(item)])
        for key, label in labels
    ]


def _named(item: object) -> bool:
    return isinstance(item, Mapping) and bool(_text(item.get("name")))


def _sections(value: object, intro: str) -> list[Mapping[str, Any]]:
    """Results saved before sections existed have one long summary. Show the rest of it as one."""
    sections = [item for item in _list(value) if isinstance(item, Mapping)]
    if sections or not intro:
        return sections
    return [{"heading": "Summary", "paragraphs": [intro], "quotes": []}]


def _split_headline(summary: str) -> tuple[str, str]:
    """A short summary is the headline. A long one, from an older result, is cut to a headline."""
    words = summary.split()
    if len(words) <= _HEADLINE_WORDS:
        return summary, ""
    first = summary.split(". ", 1)[0].rstrip(".")
    if len(first.split()) <= _HEADLINE_WORDS * 2:
        return first, summary[len(first) :].lstrip(". ")
    return " ".join(words[:_HEADLINE_WORDS]) + "...", summary


def _source(document: str, page: object) -> str:
    where = f"p. {page}" if isinstance(page, int) else ""
    return " · ".join(part for part in (document, where) if part)


def _join(values: Sequence[str]) -> str:
    return escape(", ".join(values))


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: object) -> list[str]:
    return [text for text in (_text(item) for item in _list(value)) if text]
