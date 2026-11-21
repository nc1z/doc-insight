from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.main import create_app


class _HealthySession:
    async def execute(self, _statement: object) -> None:
        return None


class _UnavailableSession:
    async def execute(self, _statement: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))


async def _healthy_session() -> AsyncIterator[_HealthySession]:
    yield _HealthySession()


async def _unavailable_session() -> AsyncIterator[_UnavailableSession]:
    yield _UnavailableSession()


def test_health() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            llm_provider="mock",
            classifier_provider="mock",
        )
    )
    application.dependency_overrides[get_session] = _healthy_session

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_database_outage() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            llm_provider="mock",
            classifier_provider="mock",
        )
    )
    application.dependency_overrides[get_session] = _unavailable_session

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 503


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
