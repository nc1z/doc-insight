"""store programmatic guardrail findings

Revision ID: 0007_guardrail_results
Revises: 0006_chunks
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_guardrail_results"
down_revision: str | Sequence[str] | None = "0006_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guardrail_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("rule", sa.String(length=64), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guardrail_results_document_id"),
        "guardrail_results",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_guardrail_results_document_id"), table_name="guardrail_results")
    op.drop_table("guardrail_results")
