from procrastinate import App, PsycopgConnector
from sqlalchemy.engine.url import make_url

PROCESS_DOCUMENT = "process_document"
CONSOLIDATE_JOB = "consolidate_job"


def build_queue(
    database_url: str,
    *,
    maintenance_cron: str = "*/15 * * * *",
    reclaim_cron: str = "* * * * *",
) -> App:
    from app.adapters.maintenance import register_maintenance
    from app.worker.tasks import register_processing

    application = App(connector=PsycopgConnector(conninfo=_conninfo(database_url)))
    register_processing(application)
    register_maintenance(application, cron=maintenance_cron, reclaim_cron=reclaim_cron)
    return application


def _conninfo(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
