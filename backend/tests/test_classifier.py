import asyncio
import json

import httpx
import pytest

from app.adapters.decision_model import CloudflareClassifier, DecisionModelClassifier
from app.adapters.factory import build_classifier
from app.core.config import Settings
from app.pipeline.models import ExtractedText
from app.pipeline.prompts import load_system_prompts
from app.pipeline.steps import check_document


class _Scores:
    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    async def injection_probability(self, text: str) -> float:
        return self._scores[text]

    async def document_type(self, text: str) -> str:
        return "letter"


def test_check_uses_the_highest_chunk_and_the_threshold() -> None:
    flagged = asyncio.run(
        check_document(
            ExtractedText(pages=[]),
            _Scores({"low": 0.7, "high": 0.71}),
            delay_seconds=0,
            chunks=["low", "high"],
            flag_threshold=0.7,
        )
    )
    equal = asyncio.run(
        check_document(
            ExtractedText(pages=[]),
            _Scores({"only": 0.7}),
            delay_seconds=0,
            chunks=["only"],
            flag_threshold=0.7,
        )
    )

    assert flagged.flagged is True
    assert flagged.score == 0.71
    assert flagged.document_type == "letter"
    assert equal.flagged is False


def test_hosted_classifier_reads_the_prompt_file() -> None:
    settings = Settings(_env_file=None, classifier_provider="jev", classifier_api_key="test-key")
    catalog = load_system_prompts(settings.system_prompts_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        assert "cf-aig-gateway-id" not in request.headers
        assert request.url.path == "/v1/systemone"
        body = json.loads(request.content)
        assert body["model"] == settings.classifier_model
        if "injection" in body["questions"]:
            assert body["state"] == "chunk"
            assert body["questions"]["injection"] == catalog.get("injection").api_question()
            return httpx.Response(200, json={"answers": {"injection": {"noul": 0.91}}})
        assert body["state"] == "memo"
        assert body["questions"]["document_type"] == catalog.get("document_type").api_question()
        return httpx.Response(200, json={"answers": {"document_type": {"choice": "letter"}}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.typesafe.ai",
    )
    classifier = DecisionModelClassifier(
        model=settings.classifier_model,
        api_key="test-key",
        base_url="https://api.typesafe.ai",
        timeout=settings.classifier_timeout_seconds,
        catalog=catalog,
        client=client,
    )

    assert asyncio.run(classifier.injection_probability("chunk")) == 0.91
    assert asyncio.run(classifier.document_type("memo")) == "letter"
    asyncio.run(client.aclose())


def test_hosted_classifier_rejects_an_unknown_document_type() -> None:
    settings = Settings(_env_file=None)
    catalog = load_system_prompts(settings.system_prompts_path)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answers": {"document_type": {"choice": "not-a-type"}}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    classifier = DecisionModelClassifier(
        model="jev",
        api_key="test-key",
        base_url="https://api.typesafe.ai",
        timeout=30,
        catalog=catalog,
        client=client,
    )

    with pytest.raises(ValueError, match="Unknown document type"):
        asyncio.run(classifier.document_type("memo"))
    asyncio.run(client.aclose())


def test_cloudflare_classifier_wraps_the_evaluation_request() -> None:
    settings = Settings(
        _env_file=None,
        classifier_provider="cloudflare",
        classifier_api_key="test-key",
        cloudflare_account_id="acct",
    )
    catalog = load_system_prompts(settings.system_prompts_path)
    built = CloudflareClassifier.from_settings(settings)

    assert isinstance(build_classifier(settings), CloudflareClassifier)
    assert built._url == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert built._headers == {"cf-aig-gateway-id": "default"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["cf-aig-gateway-id"] == "default"
        assert request.url.path == "/client/v4/accounts/acct/ai/run"
        body = json.loads(request.content)
        assert body["model"] == "typesafe/jev"
        assert body["input"]["state"] == "chunk"
        question = catalog.get("injection").api_question()
        assert body["input"]["questions"]["injection"] == question
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "state": "Completed",
                    "result": {"answers": {"injection": {"noul": 0.88}}},
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    classifier = CloudflareClassifier(
        model=settings.classifier_model,
        api_key="test-key",
        base_url="https://api.cloudflare.com/client/v4/accounts/acct",
        timeout=30,
        catalog=catalog,
        client=client,
        endpoint="/ai/run",
        wrap_input=True,
        headers={"cf-aig-gateway-id": "default"},
    )

    assert asyncio.run(classifier.injection_probability("chunk")) == 0.88
    asyncio.run(client.aclose())
