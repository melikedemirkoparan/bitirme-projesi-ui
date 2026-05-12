"""patent: add nullable domain column

Revision ID: 9a2b3c4d5e6f
Revises: 8d1f2a3b4c5e
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a2b3c4d5e6f"
down_revision: Union[str, None] = "8d1f2a3b4c5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Free-text technical domain used by the RAG retrieval Stage A
    # (semantic match against description_title_en) to narrow the
    # candidate definitions before element-name semantic ranking.
    # Nullable so existing patents continue to work — Stage A is simply
    # skipped for them.
    op.add_column(
        "patent",
        sa.Column("domain", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patent", "domain")
