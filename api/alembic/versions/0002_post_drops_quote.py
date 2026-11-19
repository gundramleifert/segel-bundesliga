"""A post has no separate quote any more: the editor's quote button makes one in the text.

Revision ID: 0002_post_drops_quote
Revises: 7133017ca682
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_post_drops_quote"
down_revision: str | None = "7133017ca682"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("post", "quote_by")
    op.drop_column("post", "quote")


def downgrade() -> None:
    op.add_column("post", sa.Column("quote", sa.String(length=500), nullable=True))
    op.add_column("post", sa.Column("quote_by", sa.String(length=120), nullable=True))
