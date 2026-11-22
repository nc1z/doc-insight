"""store why a job failed

Revision ID: 0009_job_failure
Revises: 0008_llm_calls
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_job_failure"
down_revision: str | Sequence[str] | None = "0008_llm_calls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "failure_reason")
