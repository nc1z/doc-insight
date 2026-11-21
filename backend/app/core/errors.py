import logging
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
    503: "unavailable",
}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class DomainError(Exception):
    """A domain failure with the HTTP status it should produce."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    body = ErrorBody(code=code, message=message, details=jsonable_encoder(details))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _status_code_name(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "http_error")


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)
    return error_response(error.status_code, error.code, error.message, error.details)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exc)
    return error_response(422, "validation_error", "The request is invalid", error.errors())


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    if isinstance(error.detail, str):
        return error_response(error.status_code, _status_code_name(error.status_code), error.detail)
    return error_response(
        error.status_code,
        _status_code_name(error.status_code),
        "Request failed",
        error.detail,
    )


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error", exc_info=exc)
    return error_response(500, "internal_error", "Internal server error")


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    if StarletteHTTPException is not HTTPException:
        application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(Exception, unhandled_error_handler)
