from app.core.config import Settings

_INJECTION = "ignore previous instructions"
_DISCUSSION = "prompt injection"


class MockClassifier:
    """Scores one fixed phrase at 0.99. A text that discusses prompt injection scores 0."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockClassifier:
        return cls()

    async def injection_probability(self, text: str) -> float:
        lowered = text.lower()
        if _INJECTION in lowered and _DISCUSSION not in lowered:
            return 0.99
        return 0.0

    async def document_type(self, text: str) -> str:
        return "other"
