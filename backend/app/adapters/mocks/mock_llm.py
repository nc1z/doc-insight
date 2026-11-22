import json
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.domain.ports import LLMRequest
from app.pipeline.prompts import llm_call_key

SummaryT = TypeVar("SummaryT", bound=BaseModel)


class MockLLM:
    """Returns the same JSON for the same prompt. It does not call a model."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockLLM:
        return cls()

    async def complete(self, request: LLMRequest, output_type: type[SummaryT]) -> SummaryT:
        llm_call_key("mock", request.prompt_id, request.prompt_version)
        fields = _fields(request.user)
        if request.prompt_id == "document_combine":
            filename = fields["filename"]
            return output_type.model_validate(
                {
                    "title": filename,
                    "inferred_type": fields.get("document_type", "other"),
                    "summary": f"Mock summary of {filename}.",
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
        if request.prompt_id == "consolidation":
            summaries = json.loads(fields.get("summaries", "[]"))
            titles = [item["title"] for item in summaries]
            names = ", ".join(titles) if titles else "no documents"
            return output_type.model_validate(
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
                    "flagged_documents": json.loads(fields.get("flagged", "[]")),
                    "excluded_files": json.loads(fields.get("excluded", "[]")),
                }
            )
        raise ValueError(f"Unknown mock prompt: {request.prompt_id}")


def _fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        key, separator, value = line.partition(": ")
        if separator:
            fields[key] = value
    return fields
