import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import build_file_storage
from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_session_factory, get_session
from app.core.errors import DomainError, register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.domain.ports import FileStorage


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(application.state.settings.database_url)
    application.state.session_factory = create_session_factory(engine)
    try:
        await application.state.file_storage.ensure_bucket()
        yield
    finally:
        await engine.dispose()


def create_app(
    settings: Settings | None = None,
    *,
    file_storage: FileStorage | None = None,
) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    configure_logging()
    application = FastAPI(title="Doc Insight API", lifespan=lifespan)
    register_exception_handlers(application)
    application.add_middleware(RequestContextMiddleware)
    application.state.file_storage = (
        file_storage if file_storage is not None else build_file_storage(resolved)
    )

    def settings_dependency() -> Settings:
        return resolved

    # Each app instance serves the settings it was built with.
    application.dependency_overrides[get_settings] = settings_dependency
    application.state.settings = resolved

    @application.get("/health")
    async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logging.getLogger("app.health").exception("database health check failed")
            raise DomainError(
                status_code=503,
                code="database_unavailable",
                message="The database is unavailable",
            ) from None
        return {"status": "ok"}

    return application


app = create_app()
