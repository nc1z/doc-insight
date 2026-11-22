import asyncio

import httpx2
import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.adapters.summary_client import GatewaySummaryClient
from app.domain.failures import StepFailure
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

    assert summary.output.title == "Harbour Line"
    assert summary.call.model == "glm-4.7"
    assert summary.call.prompt_id == "document_combine"
    assert summary.call.prompt_version == 3
    assert summary.call.input_tokens >= 0
    assert summary.call.output_tokens >= 0
    assert summary.call.latency_ms >= 0
    assert calls == [0, 0]
    assert "CANARY-7F3A9C" in instructions[0]
    assert "glm-4.7:document_combine:v3" in caplog.text


def test_retries_stop_at_the_configured_limit() -> None:
    calls: list[int] = []

    def respond(_messages: list[object], _info: AgentInfo) -> ModelResponse:
        calls.append(1)
        return ModelResponse(parts=[TextPart(content="not json")])

    client = GatewaySummaryClient(
        model="glm-4.7",
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
        timeout=5,
        output_retries=1,
        chat=FunctionModel(respond),
    )

    with pytest.raises(StepFailure) as caught:
        asyncio.run(client.complete(_REQUEST, _Note))

    assert caught.value.code == "step_failed"
    assert caught.value.permanent is True
    assert len(calls) == 2


def test_summary_request_names_the_ai_gateway() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["cf-aig-gateway-id"] == "credits"
        return httpx2.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "@cf/zai-org/glm-5.3",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"title": "Harbour Line"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    chat = OpenAIChatModel(
        "@cf/zai-org/glm-5.3",
        provider=OpenAICompatibleProvider(
            "cloudflare",
            base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
            api_key="test-key",
            http_client=http,
        ),
    )
    client = GatewaySummaryClient(
        model="@cf/zai-org/glm-5.3",
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
        timeout=5,
        output_retries=0,
        chat=chat,
        gateway_id="credits",
    )

    summary = asyncio.run(client.complete(_REQUEST, _Note))

    assert summary.output.title == "Harbour Line"
    asyncio.run(http.aclose())
