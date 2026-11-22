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
)
from app.pipeline.prompts import SystemPromptCatalog, load_system_prompts
from app.pipeline.steps import summarise_document

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


def _prompts() -> SystemPromptCatalog:
    return load_system_prompts(Settings(_env_file=None).system_prompts_path)
