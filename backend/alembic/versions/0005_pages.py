"""store extracted text per page

Revision ID: 0005_pages
Revises: 0004_pipeline_results
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_pages"
down_revision: str | Sequence[str] | None = "0004_pipeline_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("needs_image", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number"),
    )
    op.create_index(op.f("ix_pages_document_id"), "pages", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pages_document_id"), table_name="pages")
    op.drop_table("pages")
