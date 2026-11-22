from procrastinate import App, PsycopgConnector
from sqlalchemy.engine.url import make_url

PROCESS_JOB = "process_job"


def build_queue(database_url: str, *, maintenance_cron: str = "*/15 * * * *") -> App:
    from app.adapters.maintenance import register_maintenance

    application = App(connector=PsycopgConnector(conninfo=_conninfo(database_url)))

    @application.task(name=PROCESS_JOB)
    async def process_job(job_id: str) -> None:
        """The worker claims this task in a later phase. The payload is the job id."""
        if not job_id:
            raise RuntimeError("The queued job has no id")

    register_maintenance(application, cron=maintenance_cron)
    return application


def _conninfo(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
