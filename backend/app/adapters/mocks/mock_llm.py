import json

from app.core.config import Settings


class MockLLM:
    """Returns the same JSON for the same prompt. It does not call a model."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockLLM:
        return cls()

    async def complete(self, prompt: str) -> str:
        kind, _, rest = prompt.partition("\n")
        fields = _fields(rest)
        if kind == "summarise":
            filename = fields["filename"]
            return json.dumps(
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
        if kind == "consolidate":
            filenames = json.loads(fields.get("filenames", "[]"))
            names = ", ".join(filenames) if filenames else "no documents"
            return json.dumps(
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
        raise ValueError(f"Unknown mock prompt: {kind}")


def _fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        key, separator, value = line.partition(": ")
        if separator:
            fields[key] = value
    return fields
