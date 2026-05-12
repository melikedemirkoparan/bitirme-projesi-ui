"""add invention_disclosure_document and research_report_document

Revision ID: b1a8c2d4e7f3
Revises: 9a2b3c4d5e6f
Create Date: 2026-05-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1a8c2d4e7f3"
down_revision: Union[str, None] = "9a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invention_disclosure_document",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("idf_id", sa.Integer(), nullable=False),
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
            ["idf_id"], ["invention_disclosure.idf_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_invention_disclosure_document_idf_id",
        "invention_disclosure_document",
        ["idf_id"],
    )

    op.create_table(
        "research_report_document",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("research_report_id", sa.Integer(), nullable=False),
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
            ["research_report_id"],
            ["research_report.research_report_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_research_report_document_research_report_id",
        "research_report_document",
        ["research_report_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_report_document_research_report_id",
        table_name="research_report_document",
    )
    op.drop_table("research_report_document")
    op.drop_index(
        "ix_invention_disclosure_document_idf_id",
        table_name="invention_disclosure_document",
    )
    op.drop_table("invention_disclosure_document")
