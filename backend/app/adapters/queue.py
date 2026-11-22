from procrastinate import App, PsycopgConnector
from sqlalchemy.engine.url import make_url

PROCESS_JOB = "process_job"


def build_queue(database_url: str) -> App:
    application = App(connector=PsycopgConnector(conninfo=_conninfo(database_url)))

    @application.task(name=PROCESS_JOB)
    async def process_job(job_id: str) -> None:
        """The worker claims this task in a later phase. The payload is the job id."""
        if not job_id:
            raise RuntimeError("The queued job has no id")

    return application


def _conninfo(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
