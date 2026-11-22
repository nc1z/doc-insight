import asyncio

from app.adapters.factory import build_classifier, build_llm
from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.worker.pipeline import DocumentPipeline
from app.worker.processing import bind_pipeline
from app.worker.tasks import bind_jobs


def main() -> None:
    configure_logging()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    queue = build_queue(settings.database_url, maintenance_cron=settings.maintenance_cron)
    repository = PostgresJobRepository(create_session_factory(engine), queue)
    delay = settings.mock_step_delay_seconds if settings.llm_provider == "mock" else 0
    bind_jobs(repository)
    bind_pipeline(
        DocumentPipeline(
            repository,
            build_llm(settings),
            build_classifier(settings),
            delay_seconds=delay,
        )
    )
    try:
        queue.run_worker()
    finally:
        bind_pipeline(None)
        bind_jobs(None)
        asyncio.run(engine.dispose())
