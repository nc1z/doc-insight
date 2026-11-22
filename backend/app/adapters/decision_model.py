from typing import Any

import httpx

from app.core.config import Settings
from app.pipeline.prompts import SystemPromptCatalog, load_system_prompts


class DecisionModelClassifier:
    """Asks the configured decision model. Questions come from the system prompt file."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float,
        catalog: SystemPromptCatalog,
        client: httpx.AsyncClient | None = None,
        endpoint: str = "/v1/systemone",
        wrap_input: bool = False,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}{endpoint}"
        self._timeout = timeout
        self._catalog = catalog
        self._client = client
        self._wrap_input = wrap_input

    @classmethod
    def from_settings(cls, settings: Settings) -> DecisionModelClassifier:
        return cls(
            model=settings.classifier_model,
            api_key=settings.classifier_api_key.get_secret_value(),
            base_url=settings.classifier_base_url,
            timeout=settings.classifier_timeout_seconds,
            catalog=load_system_prompts(settings.system_prompts_path),
        )

    async def injection_probability(self, text: str) -> float:
        prompt = self._catalog.get("injection")
        answers = await self._ask(prompt.render(text), {"injection": prompt.api_question()})
        try:
            return float(answers["injection"]["noul"])
        except KeyError, TypeError, ValueError:
            raise ValueError("Classifier response has no injection probability") from None

    async def document_type(self, text: str) -> str:
        prompt = self._catalog.get("document_type")
        answers = await self._ask(prompt.render(text), {"document_type": prompt.api_question()})
        try:
            choice = answers["document_type"]["choice"]
        except KeyError, TypeError:
            raise ValueError("Classifier response has no document type") from None
        if not isinstance(choice, str) or choice not in (prompt.criteria or {}):
            raise ValueError(f"Unknown document type: {choice}")
        return choice

    async def _ask(self, state: str, questions: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self._model}
        if self._wrap_input:
            payload["input"] = {"state": state, "questions": questions}
        else:
            payload["state"] = state
            payload["questions"] = questions
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                self._url,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            body = response.json()
        finally:
            if owns_client:
                await client.aclose()
        return _answers(body)


class CloudflareClassifier(DecisionModelClassifier):
    """Evaluation request for the Cloudflare AI Gateway. The model name comes from config."""

    @classmethod
    def from_settings(cls, settings: Settings) -> CloudflareClassifier:
        account = settings.cloudflare_account_id
        return cls(
            model=settings.classifier_model,
            api_key=settings.classifier_api_key.get_secret_value(),
            base_url=f"{settings.classifier_base_url.rstrip('/')}/accounts/{account}",
            timeout=settings.classifier_timeout_seconds,
            catalog=load_system_prompts(settings.system_prompts_path),
            endpoint="/ai/run",
            wrap_input=True,
        )


def _answers(body: object) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError("Classifier response has no answers")  # noqa: TRY004
    if body.get("success") is False:
        raise ValueError("Classifier request was rejected")
    result = body.get("result")
    source = result if isinstance(result, dict) else body
    # /ai/run wraps the model output again: result.state plus result.result.answers.
    inner = source.get("result")
    if isinstance(inner, dict) and isinstance(inner.get("answers"), dict):
        source = inner
    answers = source.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("Classifier response has no answers")  # noqa: TRY004
    return answers
