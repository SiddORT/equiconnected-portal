"""add signup state province

Revision ID: 08e5eba54f96
Revises: c8e1f3a6b924
Create Date: 2026-08-21 07:18:41.815011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08e5eba54f96'
down_revision: Union[str, None] = 'c8e1f3a6b924'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("state_province", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "state_province")
