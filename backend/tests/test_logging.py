import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import create_app
from tests.doubles import IdleFileStorage

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def test_json_formatter_includes_the_request() -> None:
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc-123"  # type: ignore[attr-defined]
    record.method = "GET"  # type: ignore[attr-defined]
    record.path = "/health"  # type: ignore[attr-defined]
    record.status_code = 200  # type: ignore[attr-defined]
    record.duration_ms = 4  # type: ignore[attr-defined]

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "request completed"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.request"
    assert payload["request_id"] == "abc-123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 4


def test_request_log_keeps_a_supplied_request_id(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app(
        Settings(
            _env_file=None,
            llm_provider="mock",
            classifier_provider="mock",
        ),
        file_storage=IdleFileStorage(),
    )

    @application.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    with caplog.at_level(logging.INFO, logger="app.request"), TestClient(application) as client:
        response = client.get("/ping", headers={"X-Request-ID": "trace-1"})

    assert response.headers["x-request-id"] == "trace-1"
    completed = [record for record in caplog.records if record.message == "request completed"]
    assert completed[-1].request_id == "trace-1"  # type: ignore[attr-defined]
    assert completed[-1].path == "/ping"  # type: ignore[attr-defined]
    assert completed[-1].status_code == 200  # type: ignore[attr-defined]


def test_unsafe_request_id_is_replaced() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            llm_provider="mock",
            classifier_provider="mock",
        ),
        file_storage=IdleFileStorage(),
    )

    @application.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(application) as client:
        response = client.get("/ping", headers={"X-Request-ID": "bad id"})

    request_id = response.headers["x-request-id"]
    assert request_id != "bad id"
    assert _REQUEST_ID.fullmatch(request_id)
