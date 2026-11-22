"""store document summaries and the consolidated report

Revision ID: 0004_pipeline_results
Revises: 0003_procrastinate
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_pipeline_results"
down_revision: str | Sequence[str] | None = "0003_procrastinate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary", postgresql.JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("report", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "report")
    op.drop_column("documents", "summary")
