import asyncio

from app.adapters.factory import build_classifier, build_file_storage, build_llm
from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.pipeline.prompts import load_system_prompts
from app.worker.pipeline import DocumentPipeline
from app.worker.processing import bind_pipeline
from app.worker.tasks import bind_jobs, bind_step_timeout


def main() -> None:
    configure_logging()
    settings = get_settings()
    load_system_prompts(settings.system_prompts_path)
    engine = create_engine(settings.database_url)
    queue = build_queue(settings.database_url, maintenance_cron=settings.maintenance_cron)
    repository = PostgresJobRepository(create_session_factory(engine), queue)
    delay = settings.mock_step_delay_seconds if settings.llm_provider == "mock" else 0
    bind_jobs(repository)
    bind_step_timeout(settings.step_timeout_seconds)
    bind_pipeline(
        DocumentPipeline(
            repository,
            build_llm(settings),
            build_classifier(settings),
            build_file_storage(settings),
            delay_seconds=delay,
            chunk_token_budget=settings.chunk_token_budget,
            flag_threshold=settings.classifier_flag_threshold,
        )
    )
    try:
        queue.run_worker()
    finally:
        bind_pipeline(None)
        bind_step_timeout(60)
        bind_jobs(None)
        asyncio.run(engine.dispose())
