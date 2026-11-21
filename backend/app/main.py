from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_session_factory, get_session


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(application.state.settings.database_url)
    application.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    application = FastAPI(title="Doc Insight API", lifespan=lifespan)

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
            raise HTTPException(status_code=503) from None
        return {"status": "ok"}

    return application


app = create_app()
