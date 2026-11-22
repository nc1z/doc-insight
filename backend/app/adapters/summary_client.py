import os
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai_compatible import OpenAICompatibleProvider

from app.core.config import Settings

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
    ) -> None:
        os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._output_retries = output_retries
        self._chat = chat or OpenAIChatModel(
            model,
            provider=OpenAICompatibleProvider("cloudflare", base_url=base_url, api_key=api_key),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> GatewaySummaryClient:
        account = settings.cloudflare_account_id
        root = settings.classifier_base_url.rstrip("/")
        return cls(
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=f"{root}/accounts/{account}/ai/v1",
            timeout=settings.llm_timeout_seconds,
            output_retries=settings.llm_output_retries,
        )

    async def complete(self, prompt: str, output_type: type[SummaryT]) -> SummaryT:
        agent: Agent[None, SummaryT] = Agent(
            self._chat,
            output_type=PromptedOutput(output_type),
            retries={"output": self._output_retries, "tools": 0},
            model_settings={
                "timeout": self._timeout,
                "request_timeout": self._timeout,
                "max_retries": 0,
            },
        )
        result = await agent.run(prompt)
        return result.output
