"""add the Procrastinate queue schema

Revision ID: 0003_procrastinate
Revises: 0002_jobs_documents
Create Date: 2026-11-22

"""

from collections.abc import Sequence

from alembic import op
from procrastinate.schema import SchemaManager

revision: str = "0003_procrastinate"
down_revision: str | Sequence[str] | None = "0002_jobs_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_SCHEMA = """
DO $$
DECLARE
    routine regprocedure;
BEGIN
    FOR routine IN
        SELECT p.oid::regprocedure
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate_%'
    LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS ' || routine || ' CASCADE';
    END LOOP;
END $$;
DROP TABLE IF EXISTS
    procrastinate_events,
    procrastinate_periodic_defers,
    procrastinate_jobs,
    procrastinate_workers
CASCADE;
DROP TYPE IF EXISTS
    procrastinate_job_to_defer_v1,
    procrastinate_job_event_type,
    procrastinate_job_status
CASCADE;
"""


def upgrade() -> None:
    # psycopg treats % as a placeholder. The schema uses % in RAISE messages.
    statements = SchemaManager.get_schema().replace("%", "%%")
    op.get_bind().exec_driver_sql(statements)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(_DROP_SCHEMA)
