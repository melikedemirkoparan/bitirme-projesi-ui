"""add app_setting + patent.invention_context + invention_disclosure.bbf_text

Revision ID: c2d9e1f4a8b6
Revises: b1a8c2d4e7f3
Create Date: 2026-05-06 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d9e1f4a8b6"
down_revision: Union[str, None] = "b1a8c2d4e7f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # Free-text invention context shown in the Settings modal — used by
    # the composer Technical Field section. Stored per-patent so each
    # project has its own context.
    op.add_column(
        "patent",
        sa.Column("invention_context", sa.Text(), nullable=True),
    )

    # Extracted/pasted raw BBF prose used by AI Suggest Definition.
    # Lives on invention_disclosure because it is the textual companion
    # of the BBF document(s).
    op.add_column(
        "invention_disclosure",
        sa.Column("bbf_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invention_disclosure", "bbf_text")
    op.drop_column("patent", "invention_context")
    op.drop_table("app_setting")
