"""add private horse and stable locations

Revision ID: 8828d27aea34
Revises: 8e6a1d4b2c90
Create Date: 2026-10-21 09:24:14.527967

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8828d27aea34'
down_revision: Union[str, None] = '8e6a1d4b2c90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historical horses intentionally remain custom and unlocated.
    op.add_column('horses', sa.Column('location_mode', sa.String(length=10), server_default='custom', nullable=False))
    op.add_column('horses', sa.Column('address', sa.String(length=300), nullable=True))
    op.add_column('horses', sa.Column('address_line_2', sa.String(length=300), nullable=True))
    op.add_column('horses', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column('horses', sa.Column('state_province', sa.String(length=100), nullable=True))
    op.add_column('horses', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('horses', sa.Column('postal_code', sa.String(length=32), nullable=True))
    op.add_column('horses', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('horses', sa.Column('longitude', sa.Float(), nullable=True))
    op.create_check_constraint('ck_horses_coordinates', 'horses', '(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)')
    op.create_check_constraint('ck_horses_location_mode', 'horses', "location_mode IN ('custom', 'stable')")
    op.add_column('stable_profiles', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('stable_profiles', sa.Column('longitude', sa.Float(), nullable=True))
    op.create_check_constraint('ck_stable_profiles_coordinates', 'stable_profiles', '(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)')


def downgrade() -> None:
    op.drop_constraint('ck_stable_profiles_coordinates', 'stable_profiles', type_='check')
    op.drop_column('stable_profiles', 'longitude')
    op.drop_column('stable_profiles', 'latitude')
    op.drop_constraint('ck_horses_location_mode', 'horses', type_='check')
    op.drop_constraint('ck_horses_coordinates', 'horses', type_='check')
    op.drop_column('horses', 'longitude')
    op.drop_column('horses', 'latitude')
    op.drop_column('horses', 'postal_code')
    op.drop_column('horses', 'city')
    op.drop_column('horses', 'state_province')
    op.drop_column('horses', 'country')
    op.drop_column('horses', 'address_line_2')
    op.drop_column('horses', 'address')
    op.drop_column('horses', 'location_mode')
