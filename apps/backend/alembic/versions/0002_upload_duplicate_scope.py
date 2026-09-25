"""Enforce company-scoped exact document deduplication.

Revision ID: 0002_upload_scope
Revises: 0001_core
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_upload_scope"
down_revision: str | None = "0001_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_company_sha256", "documents", ["company_id", "sha256_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_company_sha256", "documents", type_="unique")
