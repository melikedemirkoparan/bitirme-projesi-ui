"""element reference_number int -> string(10) NOT NULL

Revision ID: 8d1f2a3b4c5e
Revises: 7c0e9b41ad22
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d1f2a3b4c5e"
down_revision: Union[str, None] = "7c0e9b41ad22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert existing integer values to text, then enforce NOT NULL.
    # All NULL rows must already be removed before applying this migration.
    op.alter_column(
        "element",
        "reference_number",
        existing_type=sa.Integer(),
        type_=sa.String(length=10),
        existing_nullable=True,
        nullable=False,
        postgresql_using="reference_number::text",
    )


def downgrade() -> None:
    # Best-effort downgrade: only rows whose reference_number parses as integer
    # will round-trip cleanly. Non-numeric values would fail the cast.
    op.alter_column(
        "element",
        "reference_number",
        existing_type=sa.String(length=10),
        type_=sa.Integer(),
        existing_nullable=False,
        nullable=True,
        postgresql_using="reference_number::integer",
    )
