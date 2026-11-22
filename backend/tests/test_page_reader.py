import asyncio

import pytest
from pydantic_ai import BinaryContent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.adapters.factory import build_page_reader, register_page_reader
from app.adapters.mocks.mock_vision import MockPageReader
from app.adapters.vision_client import GatewayPageReader
from app.core.config import Settings
from app.domain.failures import StepFailure
from app.domain.ports import LLMRequest

_REQUEST = LLMRequest(
    prompt_id="page_image",
    prompt_version=1,
    system="CANARY-7F3A9C",
    user="filename: a.pdf\npage: 3\npage_text: ",
)
_IMAGE = b"\x89PNG\r\n\x1a\nfake"


def _reader(function: object) -> GatewayPageReader:
    return GatewayPageReader(
        model="@cf/google/gemma-4-26b-a4b-it",
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct/ai/v1",
        timeout=5,
        chat=FunctionModel(function),  # type: ignore[arg-type]
    )


def test_the_image_and_instructions_go_to_the_model_and_the_text_comes_back() -> None:
    seen: dict[str, object] = {}

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen["instructions"] = info.instructions
        request = messages[-1]
        assert isinstance(request, ModelRequest)
        part = next(item for item in request.parts if isinstance(item, UserPromptPart))
        seen["content"] = part.content
        return ModelResponse(parts=[TextPart(content="OpenAI: 38%")])

    reading = asyncio.run(_reader(respond).read(_REQUEST, _IMAGE))

    assert reading.text == "OpenAI: 38%"
    assert reading.call.model == "@cf/google/gemma-4-26b-a4b-it"
    assert reading.call.prompt_id == "page_image"
    assert reading.call.prompt_version == 1
    assert reading.call.latency_ms >= 0
    assert "CANARY-7F3A9C" in str(seen["instructions"])
    content = seen["content"]
    assert isinstance(content, list)
    assert content[0] == _REQUEST.user
    image = content[1]
    assert isinstance(image, BinaryContent)
    assert image.data == _IMAGE
    assert image.media_type == "image/png"


def test_a_rejected_request_fails_the_step_without_retrying() -> None:
    def respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(status_code=404, model_name="retired", body="model not found")

    with pytest.raises(StepFailure) as caught:
        asyncio.run(_reader(respond).read(_REQUEST, _IMAGE))

    assert caught.value.permanent is True
    assert caught.value.code == "step_failed"


@pytest.mark.parametrize("status", [429, 503])
def test_a_busy_or_failing_service_is_left_for_the_step_to_retry(status: int) -> None:
    def respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(status_code=status, model_name="m", body="try later")

    with pytest.raises(ModelHTTPError):
        asyncio.run(_reader(respond).read(_REQUEST, _IMAGE))


def test_the_factory_builds_the_configured_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("VISION_PROVIDER", "LLM_API_KEY", "CLOUDFLARE_ACCOUNT_ID"):
        monkeypatch.delenv(key, raising=False)

    assert build_page_reader(Settings(_env_file=None, classifier_provider="mock")) is None
    assert isinstance(
        build_page_reader(
            Settings(_env_file=None, classifier_provider="mock", vision_provider="mock")
        ),
        MockPageReader,
    )
    live = build_page_reader(
        Settings(
            _env_file=None,
            classifier_provider="mock",
            vision_provider="cloudflare",
            llm_api_key="test-key",
            cloudflare_account_id="acct",
        )
    )
    assert isinstance(live, GatewayPageReader)


def test_another_reader_can_be_registered() -> None:
    register_page_reader("custom", lambda _settings: MockPageReader())
    settings = Settings(_env_file=None, classifier_provider="mock").model_copy(
        update={"vision_provider": "custom"}
    )

    assert isinstance(build_page_reader(settings), MockPageReader)
