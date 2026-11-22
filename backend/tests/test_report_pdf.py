import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pymupdf

from app.domain.models import Document, Job
from app.domain.status import DocumentStatus, JobStatus
from app.export.report_pdf import render_report_pdf

_SECTION = {
    "heading": "Private Rents",
    "paragraphs": ["Rents edged up 0.8 percent in October.", "Vacancy sits at 5.9 percent."],
    "quotes": [{"quote": "Rents rose 0.8 percent", "page": 1, "document": "rents.pdf"}],
}
_SUMMARY = {
    "title": "Condo Rentals",
    "inferred_type": "press_release",
    "summary": "Private rents rose 0.8 percent in October.",
    "key_points": ["Rents rose 0.8 percent.", "Vacancy is 5.9 percent."],
    "sections": [_SECTION],
    "topics": ["Rents", "Vacancy"],
    "entities": {"organisations": [{"name": "Harbourview", "aliases": []}]},
    "notable_points": [],
}
_REPORT = {
    "summary": "Rents are up and supply is steady.",
    "takeaways": ["Rents rose.", "Supply held."],
    "sections": [_SECTION],
    "themes": ["rents"],
    "contradictions": [
        {
            "about": "Resale volume",
            "claims": [
                {"text": "About 6,400 deals.", "document": "a.pdf", "page": 1, "quote": "6,400"},
                {"text": "About 7,100 deals.", "document": "b.pdf", "page": 2, "quote": "7,100"},
            ],
        }
    ],
    "entities": {},
    "flagged_documents": [],
    "excluded_files": ["left-out.pdf"],
}


def _job(report: dict[str, Any] | None, summaries: list[dict[str, Any] | None]) -> Job:
    start = datetime(2026, 11, 22, tzinfo=UTC)
    job = Job(id=uuid4(), status=JobStatus.SUCCEEDED, report=report)
    job.documents = [
        Document(
            filename=f"file-{index}.pdf",
            storage_key=f"key-{index}",
            status=DocumentStatus.SUCCEEDED,
            summary=summary,
            created_at=start + timedelta(seconds=index),
            excluded=False,
        )
        for index, summary in enumerate(summaries)
    ]
    return job


def _pages(data: bytes) -> list[str]:
    # The font joins "fi" into one character, so fold those back before comparing.
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        return [unicodedata.normalize("NFKC", str(page.get_text())) for page in pdf]


def test_the_pdf_has_one_page_for_the_overview_and_one_per_file() -> None:
    pages = _pages(render_report_pdf(_job(_REPORT, [_SUMMARY, _SUMMARY, _SUMMARY])))

    assert len(pages) == 4
    assert "Rents are up and supply is steady." in pages[0]
    assert "Resale volume" in pages[0]
    assert "left-out.pdf" in pages[0]
    assert "Private rents rose 0.8 percent in October." in pages[1]
    assert "file-0.pdf" in pages[1]
    assert "Harbourview" in pages[3]


def test_a_file_without_a_summary_still_gets_its_page() -> None:
    pages = _pages(render_report_pdf(_job(_REPORT, [_SUMMARY, None])))

    assert len(pages) == 3
    assert "This file has no summary yet." in pages[2]


def test_a_result_from_before_sections_still_renders() -> None:
    legacy_summary = {
        "summary": "A long first sentence about the quarter. " + "More detail follows here. " * 12
    }
    legacy_report = {"summary": "The documents agree on a slow quarter. " + "And so on. " * 30}

    pages = _pages(render_report_pdf(_job(legacy_report, [legacy_summary])))

    assert len(pages) == 2
    assert "The documents agree on a slow quarter" in pages[0]
    assert "A long first sentence about the quarter" in pages[1]


def test_full_pages_are_scaled_down_instead_of_spilling_over() -> None:
    crowded = {
        **_SUMMARY,
        "sections": [{**_SECTION, "paragraphs": ["A long paragraph. " * 18] * 4}] * 3,
    }

    pages = _pages(render_report_pdf(_job(_REPORT, [crowded])))

    assert len(pages) == 2


def test_markup_in_a_document_is_shown_as_text() -> None:
    hostile = {**_SUMMARY, "summary": "<b>Bold</b> & <script>x</script>"}

    pages = _pages(render_report_pdf(_job(_REPORT, [hostile])))

    assert "<b>Bold</b> & <script>x</script>" in pages[1]
