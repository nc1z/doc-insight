import asyncio
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.core.db import create_engine, get_session
from app.main import create_app
from tests.doubles import IdleFileStorage


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
        ),
        file_storage=IdleFileStorage(),
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
        ),
        file_storage=IdleFileStorage(),
    )
    application.dependency_overrides[get_session] = _unavailable_session

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "code": "database_unavailable",
        "message": "The database is unavailable",
        "details": None,
    }


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


async def _alembic_version(database_url: str) -> str:
    engine = create_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar_one()
    finally:
        await engine.dispose()
    return str(version)


def test_migrations_apply_job_tables(migrated_database_url: str) -> None:
    assert asyncio.run(_alembic_version(migrated_database_url)) == "0006_chunks"


def test_health_reads_migrated_database(migrated_database_url: str) -> None:
    application = create_app(
        Settings(
            _env_file=None,
            database_url=migrated_database_url,
            llm_provider="mock",
            classifier_provider="mock",
        ),
        file_storage=IdleFileStorage(),
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]
