import json
import logging
import re
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if isinstance(record.exc_info, tuple):
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _record_factory(previous: Any) -> Any:
    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    return factory


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    logging.setLogRecordFactory(_record_factory(logging.getLogRecordFactory()))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _header_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            candidate = value.decode("latin-1").strip()
            if _REQUEST_ID.fullmatch(candidate):
                return candidate
            return None
    return None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header_request_id(scope) or str(uuid4())
        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            # Starlette turns this into a response outside this middleware, which
            # would drop the request ID. Handle it here while the ID is still set.
            if response_started:
                raise
            logging.getLogger("app.errors").error("unhandled error", exc_info=exc)
            response = error_response(500, "internal_error", "Internal server error")
            await response(scope, receive, send_with_request_id)
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            try:
                logging.getLogger("app.request").info(
                    "request completed",
                    extra={
                        "method": scope.get("method", ""),
                        "path": scope.get("path", ""),
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            finally:
                request_id_var.reset(token)
