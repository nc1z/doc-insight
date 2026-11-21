import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine.url import make_url

# The postgres-test compose service publishes this port. The app database stays on 5432.
_TEST_PORT = 5433


def _connect(admin_url: str) -> psycopg.Connection[tuple[object, ...]]:
    sync_url = make_url(admin_url).set(drivername="postgresql")
    try:
        return psycopg.connect(sync_url.render_as_string(hide_password=False), autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.fail(
            "The test Postgres container is not available. "
            "Start it with `docker compose up -d postgres-test --wait`. "
            f"({exc})"
        )


def _recreate_database(admin_url: str, name: str) -> None:
    if make_url(admin_url).database == name:
        pytest.fail(f"Refusing to recreate the admin database {name}")
    connection = _connect(admin_url)
    try:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (name,),
        )
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        connection.close()


def _drop_database(admin_url: str, name: str) -> None:
    connection = _connect(admin_url)
    try:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (name,),
        )
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    finally:
        connection.close()


def _postgres_setting(name: str, default: str) -> str:
    if value := os.environ.get(name):
        return value
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, raw = stripped.split("=", 1)
            if key == name:
                return raw.strip().strip('"').strip("'")
    return default


def _admin_url() -> str:
    return (
        make_url(f"postgresql+psycopg://localhost:{_TEST_PORT}/postgres")
        .set(
            username=_postgres_setting("TEST_POSTGRES_USER", "docinsight"),
            password=_postgres_setting("TEST_POSTGRES_PASSWORD", "docinsight"),
        )
        .render_as_string(hide_password=False)
    )


@pytest.fixture(scope="session")
def migrated_database_url() -> Iterator[str]:
    admin_url = _admin_url()
    test_database = _postgres_setting("TEST_POSTGRES_DB", "docinsight_test")
    test_url = make_url(admin_url).set(database=test_database)
    rendered = test_url.render_as_string(hide_password=False)
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("prepend_sys_path", str(backend_dir))
    config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))

    _recreate_database(admin_url, test_database)
    try:
        command.upgrade(config, "head")
        yield rendered
    finally:
        _drop_database(admin_url, test_database)
