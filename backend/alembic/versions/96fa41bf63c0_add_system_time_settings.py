"""add system time settings

Revision ID: 96fa41bf63c0
Revises: f7c1d4e8a901
Create Date: 2026-08-21 17:19:18.206973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96fa41bf63c0'
down_revision: Union[str, None] = 'f7c1d4e8a901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('system_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
    sa.Column('date_format', sa.String(length=32), server_default='month_day_year', nullable=False),
    sa.Column('time_format', sa.String(length=16), server_default='12_hour', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("date_format IN ('month_day_year', 'day_month_year', 'year_month_day')", name='ck_system_settings_date_format'),
    sa.CheckConstraint("time_format IN ('12_hour', '24_hour')", name='ck_system_settings_time_format'),
    sa.CheckConstraint('id = 1', name='ck_system_settings_singleton'),
    sa.PrimaryKeyConstraint('id')
    )
    op.execute(
        """
        INSERT INTO system_settings
            (id, timezone, date_format, time_format, created_at, updated_at)
        VALUES
            (1, 'UTC', 'month_day_year', '12_hour', now(), now())
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table('system_settings')
