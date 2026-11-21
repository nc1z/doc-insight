import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import DomainError
from app.main import create_app
from tests.doubles import IdleFileStorage


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = create_app(
        Settings(
            _env_file=None,
            llm_provider="mock",
            classifier_provider="mock",
        ),
        file_storage=IdleFileStorage(),
    )

    @application.get("/boom")
    async def boom() -> None:
        raise DomainError(
            status_code=409,
            code="invalid_transition",
            message="Job cannot move to that status",
            details={"to": "cancelled"},
        )

    @application.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret boom")

    @application.get("/needs-int")
    async def needs_int(count: int) -> dict[str, int]:
        return {"count": count}

    with TestClient(application) as test_client:
        yield test_client


def test_domain_error_uses_error_schema(client: TestClient) -> None:
    response = client.get("/boom", headers={"X-Request-ID": "abc-123"})

    assert response.status_code == 409
    assert response.json() == {
        "code": "invalid_transition",
        "message": "Job cannot move to that status",
        "details": {"to": "cancelled"},
    }
    assert response.headers["x-request-id"] == "abc-123"


def test_unknown_route_uses_error_schema(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "message": "Not Found",
        "details": None,
    }
    assert response.headers["x-request-id"]


def test_validation_error_uses_error_schema(client: TestClient) -> None:
    response = client.get("/needs-int?count=nope")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "The request is invalid"
    assert isinstance(body["details"], list)
    assert body["details"][0]["loc"][-1] == "count"


def test_unhandled_error_hides_the_exception(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        response = client.get("/crash", headers={"X-Request-ID": "err-1"})

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "err-1"
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
    }
    assert "secret boom" not in response.text
    assert caplog.records[-1].request_id == "err-1"  # type: ignore[attr-defined]
