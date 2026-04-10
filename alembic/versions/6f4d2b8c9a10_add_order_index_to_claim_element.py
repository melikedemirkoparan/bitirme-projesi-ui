"""add order_index to claim_element

Revision ID: 6f4d2b8c9a10
Revises: a953e5ca1012
Create Date: 2026-04-10 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f4d2b8c9a10"
down_revision: Union[str, Sequence[str], None] = "a953e5ca1012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "claim_element",
        sa.Column("order_index", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        WITH ranked_links AS (
            SELECT
                claim_element_id,
                ROW_NUMBER() OVER (
                    PARTITION BY claim_id
                    ORDER BY created_at, claim_element_id
                ) AS next_order
            FROM claim_element
        )
        UPDATE claim_element AS ce
        SET order_index = ranked_links.next_order
        FROM ranked_links
        WHERE ce.claim_element_id = ranked_links.claim_element_id
        """
    )

    op.alter_column("claim_element", "order_index", nullable=False)


def downgrade() -> None:
    op.drop_column("claim_element", "order_index")
