import json
import time
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.domain.ports import LLMCall, LLMRequest, LLMResult
from app.pipeline.prompts import llm_call_key

SummaryT = TypeVar("SummaryT", bound=BaseModel)


class MockLLM:
    """Returns the same JSON for the same prompt. It does not call a model."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockLLM:
        return cls()

    async def complete(
        self, request: LLMRequest, output_type: type[SummaryT]
    ) -> LLMResult[SummaryT]:
        started = time.perf_counter()
        llm_call_key("mock", request.prompt_id, request.prompt_version)
        fields = _fields(request.user)
        output: SummaryT
        if request.prompt_id == "chunk_output":
            filename = fields["filename"]
            page = int(fields.get("page", "1"))
            output = output_type.model_validate(
                {
                    "topics": ["mock"],
                    "entities": {
                        "people": [],
                        "organisations": [],
                        "locations": [],
                        "dates": [],
                    },
                    "notable_points": [
                        {
                            "text": "Mock point",
                            "page": page,
                            "quote": f"{filename} page {page}",
                        }
                    ],
                }
            )
        elif request.prompt_id == "document_combine":
            filename = fields["filename"]
            output = output_type.model_validate(
                {
                    "title": filename,
                    "inferred_type": fields.get("document_type", "other"),
                    "summary": f"Mock summary of {filename}.",
                    "key_points": ["Mock key point"],
                    "sections": [{"heading": "Mock heading", "paragraphs": ["Mock paragraph."]}],
                    "topics": ["mock"],
                    "entities": {
                        "people": [],
                        "organisations": [],
                        "locations": [],
                        "dates": [],
                    },
                    "notable_points": [
                        {
                            "text": "Mock point",
                            "page": 1,
                            "quote": f"{filename} page 1",
                        }
                    ],
                }
            )
        elif request.prompt_id == "consolidation":
            summaries = json.loads(fields.get("summaries", "[]"))
            titles = [item["title"] for item in summaries]
            names = ", ".join(titles) if titles else "no documents"
            output = output_type.model_validate(
                {
                    "summary": f"Mock report of {names}.",
                    "themes": ["mock"],
                    "contradictions": [],
                    "entities": {
                        "people": [],
                        "organisations": [],
                        "locations": [],
                        "dates": [],
                    },
                    "takeaways": ["Mock takeaway"],
                    "sections": [{"heading": "Mock heading", "paragraphs": ["Mock paragraph."]}],
                    "flagged_documents": json.loads(fields.get("flagged", "[]")),
                    "excluded_files": json.loads(fields.get("excluded", "[]")),
                }
            )
        else:
            raise ValueError(f"Unknown mock prompt: {request.prompt_id}")
        return LLMResult(output=output, call=_call(request, started))


def _call(request: LLMRequest, started: float) -> LLMCall:
    return LLMCall(
        model="mock",
        prompt_id=request.prompt_id,
        prompt_version=request.prompt_version,
        input_tokens=0,
        output_tokens=0,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


def _fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        key, separator, value = line.partition(": ")
        if separator:
            fields[key] = value
    return fields
