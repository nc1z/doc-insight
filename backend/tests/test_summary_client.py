import asyncio

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.adapters.summary_client import GatewaySummaryClient
from app.domain.ports import LLMRequest

_REQUEST = LLMRequest(
    prompt_id="document_combine",
    prompt_version=3,
    system="CANARY-7F3A9C",
    user="summarise the memo",
)


class _Note(BaseModel):
    title: str


def test_a_summary_that_does_not_match_is_asked_again(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[int] = []
    instructions: list[str] = []

    def respond(_messages: list[object], info: AgentInfo) -> ModelResponse:
        calls.append(len(info.function_tools) + len(info.output_tools))
        instructions.append(info.instructions or "")
        if len(calls) == 1:
            return ModelResponse(parts=[TextPart(content="not json")])
        return ModelResponse(parts=[TextPart(content='{"title": "Harbour Line"}')])

    client = GatewaySummaryClient(
        model="glm-4.7",
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
        timeout=5,
        output_retries=1,
        chat=FunctionModel(respond),
    )

    with caplog.at_level("INFO", logger="app.llm"):
        summary = asyncio.run(client.complete(_REQUEST, _Note))

    assert summary.title == "Harbour Line"
    assert calls == [0, 0]
    assert "CANARY-7F3A9C" in instructions[0]
    assert "glm-4.7:document_combine:v3" in caplog.text


def test_retries_stop_at_the_configured_limit() -> None:
    def respond(_messages: list[object], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="not json")])

    client = GatewaySummaryClient(
        model="glm-4.7",
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
        timeout=5,
        output_retries=1,
        chat=FunctionModel(respond),
    )

    with pytest.raises(UnexpectedModelBehavior):
        asyncio.run(client.complete(_REQUEST, _Note))
