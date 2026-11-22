from app.core.config import Settings
from app.domain.ports import Classification

_INJECTION = "ignore previous instructions"


class MockClassifier:
    """Flags one fixed phrase. Every other text is benign."""

    @classmethod
    def from_settings(cls, _settings: Settings) -> MockClassifier:
        return cls()

    async def classify(self, text: str) -> Classification:
        if _INJECTION in text.lower():
            return Classification(label="injection", score=0.99)
        return Classification(label="benign", score=0.0)
