import logging
import os
import time

from pydantic_ai import Agent, BinaryContent, ModelSettings
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.core.config import Settings
from app.domain.failures import StepFailure
from app.domain.ports import LLMCall, LLMRequest, PageReading
from app.pipeline.prompts import llm_call_key

logger = logging.getLogger("app.vision")

# A page transcription is short. The cap keeps one odd answer from running for minutes.
_MAX_TOKENS = 1500
# Other 4xx answers mean the request itself is wrong, such as a retired model. Asking again
# will not help, so the step fails at once. These few can pass on a later try.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429})


class GatewayPageReader:
    """Sends a page image and its instructions to a chat model that can see pictures."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float,
        chat: Model | None = None,
        gateway_id: str = "",
    ) -> None:
        os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
        self._model = model
        self._timeout = timeout
        self._gateway_id = gateway_id
        self._chat = chat or OpenAIChatModel(
            model,
            provider=OpenAICompatibleProvider("cloudflare", base_url=base_url, api_key=api_key),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> GatewayPageReader:
        account = settings.cloudflare_account_id
        root = settings.llm_base_url.rstrip("/")
        return cls(
            model=settings.vision_model,
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=f"{root}/accounts/{account}/ai/v1",
            timeout=settings.llm_timeout_seconds,
            gateway_id=settings.cloudflare_ai_gateway_id,
        )

    async def read(self, request: LLMRequest, image: bytes) -> PageReading:
        key = llm_call_key(self._model, request.prompt_id, request.prompt_version)
        started = time.perf_counter()
        model_settings: ModelSettings = {
            "timeout": self._timeout,
            "request_timeout": self._timeout,
            "max_retries": 0,
            "max_tokens": _MAX_TOKENS,
            "temperature": 0,
        }
        if self._gateway_id:
            model_settings["extra_headers"] = {"cf-aig-gateway-id": self._gateway_id}
        agent: Agent[None, str] = Agent(self._chat, output_type=str, model_settings=model_settings)
        try:
            result = await agent.run(
                [request.user, BinaryContent(data=image, media_type="image/png")],
                instructions=request.system,
                metadata={
                    "prompt_id": request.prompt_id,
                    "prompt_version": request.prompt_version,
                    "cache_key": key,
                },
            )
        except ModelHTTPError as exc:
            if 400 <= exc.status_code < 500 and exc.status_code not in _RETRYABLE_STATUS:
                logger.error(
                    "vision model %s rejected the request (%s). Check VISION_MODEL.",
                    self._model,
                    exc.status_code,
                )
                raise StepFailure("step_failed", permanent=True) from exc
            raise
        except UnexpectedModelBehavior as exc:
            raise StepFailure("step_failed", permanent=True) from exc
        usage = result.usage
        return PageReading(
            text=result.output,
            call=LLMCall(
                model=self._model,
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=int((time.perf_counter() - started) * 1000),
            ),
        )
