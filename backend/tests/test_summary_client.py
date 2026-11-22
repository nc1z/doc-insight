import asyncio

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.adapters.summary_client import GatewaySummaryClient


class _Note(BaseModel):
    title: str


def test_a_summary_that_does_not_match_is_asked_again() -> None:
    calls: list[int] = []

    def respond(_messages: list[object], info: AgentInfo) -> ModelResponse:
        calls.append(len(info.function_tools) + len(info.output_tools))
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

    summary = asyncio.run(client.complete("summarise the memo", _Note))

    assert summary.title == "Harbour Line"
    assert calls == [0, 0]


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
        asyncio.run(client.complete("summarise the memo", _Note))
