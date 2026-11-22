from app.core.config import Settings

_INJECTION = "ignore previous instructions"


class MockClassifier:
    """Scores one fixed phrase at 0.99. Every other text scores 0. Document type is other."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockClassifier:
        return cls()

    async def injection_probability(self, text: str) -> float:
        if _INJECTION in text.lower():
            return 0.99
        return 0.0

    async def document_type(self, text: str) -> str:
        return "other"
