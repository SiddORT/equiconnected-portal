"""add_name_to_provider_locations

Revision ID: d8912e12cf71
Revises: 781951970595
Create Date: 2026-08-19 04:30:27.328911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8912e12cf71'
down_revision: Union[str, None] = '781951970595'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('provider_locations', sa.Column('name', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('provider_locations', 'name')
