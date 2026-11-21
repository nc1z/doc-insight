from fastapi import FastAPI

from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    application = FastAPI(title="Doc Insight API")

    def settings_dependency() -> Settings:
        return resolved

    # Each app instance serves the settings it was built with.
    application.dependency_overrides[get_settings] = settings_dependency
    application.state.settings = resolved

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
