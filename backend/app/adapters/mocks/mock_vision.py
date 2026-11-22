from app.core.config import Settings
from app.domain.ports import LLMCall, LLMRequest, PageReading

MOCK_IMAGE_TEXT = "Mock text read from the images on this page."


class MockPageReader:
    """A reader that needs no model. It always finds the same short line."""

    @classmethod
    def from_settings(cls, settings: Settings) -> MockPageReader:
        return cls()

    async def read(self, request: LLMRequest, image: bytes) -> PageReading:
        return PageReading(
            text=MOCK_IMAGE_TEXT,
            call=LLMCall(
                model="mock-vision",
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
            ),
        )
