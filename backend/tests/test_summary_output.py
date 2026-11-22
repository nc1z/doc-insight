import asyncio

from pydantic import BaseModel

from app.adapters.mocks.mock_llm import MockLLM
from app.core.config import Settings
from app.domain.ports import LLMRequest, LLMResult
from app.pipeline.models import (
    CheckResult,
    ExtractedText,
    ExtractInput,
    PageChunk,
    PageText,
    PullQuote,
    Section,
)
from app.pipeline.prompts import SystemPromptCatalog, load_system_prompts
from app.pipeline.steps import _verified_for_report, _verified_section, summarise_document

_CHECK = CheckResult(flagged=False, label="benign", score=0.1, document_type="letter")


def test_mock_output_keeps_a_quote_that_is_on_the_page() -> None:
    summary, calls = asyncio.run(
        summarise_document(
            ExtractInput(filename="desk-note.pdf", page_count=1),
            ExtractedText(pages=[PageText(page=1, text="desk-note.pdf page 1")]),
            _CHECK,
            MockLLM(),
            _prompts(),
            [PageChunk(page=1, text="desk-note.pdf page 1", token_count=4)],
            delay_seconds=0,
        )
    )

    assert summary.summary == "Mock summary of desk-note.pdf."
    assert [(point.page, point.quote) for point in summary.notable_points] == [
        (1, "desk-note.pdf page 1")
    ]
    assert [call.prompt_id for call in calls] == ["chunk_output", "document_combine"]


def test_mock_output_drops_a_quote_from_the_wrong_page() -> None:
    seen: list[str] = []

    class _Recording:
        def __init__(self) -> None:
            self._mock = MockLLM()

        async def complete[SummaryT: BaseModel](
            self,
            request: LLMRequest,
            output_type: type[SummaryT],
        ) -> LLMResult[SummaryT]:
            if request.prompt_id == "document_combine":
                seen.append(request.user)
            return await self._mock.complete(request, output_type)

    summary, _calls = asyncio.run(
        summarise_document(
            ExtractInput(filename="desk-note.pdf", page_count=1),
            ExtractedText(pages=[PageText(page=1, text="The cost is $420 million today")]),
            _CHECK,
            _Recording(),
            _prompts(),
            [PageChunk(page=1, text="The cost is $420 million today", token_count=6)],
            delay_seconds=0,
        )
    )

    assert summary.summary == "Mock summary of desk-note.pdf."
    assert summary.notable_points == []
    assert '"notable_points": []' in seen[0]


def test_section_keeps_only_pull_quotes_found_on_their_page() -> None:
    section = Section(
        heading="Cost",
        paragraphs=["The cost is high."],
        quotes=[
            PullQuote(quote="The cost is $420 million", page=1),
            PullQuote(quote="The cost is $420 million", page=2),
        ],
    )
    invented = Section(
        heading="Cost",
        paragraphs=["The cost is high."],
        quotes=[PullQuote(quote="Invented words", page=1)],
    )
    page = [PageText(page=1, text="The cost is $420 million today")]
    assert _verified_section(invented, page, "desk-note.pdf").quotes == []

    kept = _verified_section(
        section, [PageText(page=1, text="The cost is $420\nmillion today")], "desk-note.pdf"
    )

    assert [(q.quote, q.page, q.document) for q in kept.quotes] == [
        ("The cost is $420 million", 1, "desk-note.pdf")
    ]


def test_report_section_keeps_only_quotes_a_document_summary_holds() -> None:
    mock = asyncio.run(
        summarise_document(
            ExtractInput(filename="a.pdf", page_count=1),
            ExtractedText(pages=[PageText(page=1, text="a.pdf page 1")]),
            _CHECK,
            MockLLM(),
            _prompts(),
            [PageChunk(page=1, text="a.pdf page 1", token_count=4)],
            delay_seconds=0,
        )
    )[0]
    section = Section(
        heading="Cost",
        paragraphs=["The cost is high."],
        quotes=[
            PullQuote(quote="a.pdf ^ page 1", page=1, document="a.pdf"),
            PullQuote(quote="Invented words", page=1, document="a.pdf"),
        ],
    )

    kept = _verified_for_report(section, [mock])

    assert [q.quote for q in kept.quotes] == ["a.pdf page 1"]


def _prompts() -> SystemPromptCatalog:
    return load_system_prompts(Settings(_env_file=None).system_prompts_path)
