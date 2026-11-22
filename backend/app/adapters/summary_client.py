import os
import time
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings, PromptedOutput
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.core.config import Settings
from app.domain.failures import StepFailure
from app.domain.ports import LLMCall, LLMRequest, LLMResult
from app.pipeline.prompts import llm_call_key

SummaryT = TypeVar("SummaryT", bound=BaseModel)


class GatewaySummaryClient:
    """Asks the configured chat model for a summary that matches the schema."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float,
        output_retries: int,
        chat: Model | None = None,
        gateway_id: str = "",
    ) -> None:
        os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._output_retries = output_retries
        self._gateway_id = gateway_id
        self._chat = chat or OpenAIChatModel(
            model,
            provider=OpenAICompatibleProvider("cloudflare", base_url=base_url, api_key=api_key),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> GatewaySummaryClient:
        account = settings.cloudflare_account_id
        root = settings.llm_base_url.rstrip("/")
        return cls(
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=f"{root}/accounts/{account}/ai/v1",
            timeout=settings.llm_timeout_seconds,
            output_retries=settings.llm_output_retries,
            gateway_id=settings.cloudflare_ai_gateway_id,
        )

    async def complete(
        self, request: LLMRequest, output_type: type[SummaryT]
    ) -> LLMResult[SummaryT]:
        key = llm_call_key(self._model, request.prompt_id, request.prompt_version)
        started = time.perf_counter()
        model_settings: ModelSettings = {
            "timeout": self._timeout,
            "request_timeout": self._timeout,
            "max_retries": 0,
        }
        if self._gateway_id:
            model_settings["extra_headers"] = {"cf-aig-gateway-id": self._gateway_id}
        agent: Agent[None, SummaryT] = Agent(
            self._chat,
            output_type=PromptedOutput(output_type),
            retries={"output": self._output_retries, "tools": 0},
            model_settings=model_settings,
        )
        try:
            result = await agent.run(
                request.user,
                instructions=request.system,
                metadata={
                    "prompt_id": request.prompt_id,
                    "prompt_version": request.prompt_version,
                    "cache_key": key,
                },
            )
        except UnexpectedModelBehavior as exc:
            raise StepFailure("step_failed", permanent=True) from exc
        usage = result.usage
        return LLMResult(
            output=result.output,
            call=LLMCall(
                model=self._model,
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=int((time.perf_counter() - started) * 1000),
            ),
        )
