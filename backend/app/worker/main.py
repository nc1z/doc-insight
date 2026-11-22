import asyncio

from app.adapters.jobs import PostgresJobRepository
from app.adapters.queue import build_queue
from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.core.logging import configure_logging
from app.worker.tasks import bind_jobs


def main() -> None:
    configure_logging()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    queue = build_queue(settings.database_url, maintenance_cron=settings.maintenance_cron)
    bind_jobs(PostgresJobRepository(create_session_factory(engine), queue))
    try:
        queue.run_worker()
    finally:
        bind_jobs(None)
        asyncio.run(engine.dispose())
