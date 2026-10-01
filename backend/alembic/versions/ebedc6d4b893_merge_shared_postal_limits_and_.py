"""merge shared postal limits and analytics migrations

Revision ID: ebedc6d4b893
Revises: 8307cdf254f3, e3b5a49c1d72
Create Date: 2026-10-01 04:47:37.653701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ebedc6d4b893'
down_revision: Union[str, None] = ('8307cdf254f3', 'e3b5a49c1d72')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
