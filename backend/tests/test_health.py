from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app, create_app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_factory_binds_settings_for_dependencies() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        classifier_provider="mock",
        max_file_count=4,
    )
    application = create_app(settings)

    assert application.state.settings is settings
    assert application.dependency_overrides[get_settings]() is settings
