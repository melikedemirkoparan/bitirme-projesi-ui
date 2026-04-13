"""add inventor_qa_document

Revision ID: 7c0e9b41ad22
Revises: 6f4d2b8c9a10
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c0e9b41ad22"
down_revision: Union[str, Sequence[str], None] = "6f4d2b8c9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventor_qa_document",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("qna_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("stored_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["qna_id"], ["inventor_qa.qna_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_inventor_qa_document_qna_id",
        "inventor_qa_document",
        ["qna_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventor_qa_document_qna_id", table_name="inventor_qa_document")
    op.drop_table("inventor_qa_document")
