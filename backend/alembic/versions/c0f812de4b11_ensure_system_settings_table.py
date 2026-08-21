"""ensure system settings table exists for upgraded environments

Revision ID: c0f812de4b11
Revises: b35196334e9b
Create Date: 2026-08-21 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0f812de4b11"
down_revision: Union[str, None] = "b35196334e9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Repair development databases stamped before the time-settings DDL ran."""
    if context.is_offline_mode():
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER NOT NULL,
                timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL,
                date_format VARCHAR(32) DEFAULT 'month_day_year' NOT NULL,
                time_format VARCHAR(16) DEFAULT '12_hour' NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                CONSTRAINT ck_system_settings_date_format
                    CHECK (date_format IN ('month_day_year', 'day_month_year', 'year_month_day')),
                CONSTRAINT ck_system_settings_time_format
                    CHECK (time_format IN ('12_hour', '24_hour')),
                CONSTRAINT ck_system_settings_singleton CHECK (id = 1),
                PRIMARY KEY (id)
            )
            """
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
        return

    if sa.inspect(op.get_bind()).has_table("system_settings"):
        return

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column(
            "date_format",
            sa.String(length=32),
            server_default="month_day_year",
            nullable=False,
        ),
        sa.Column("time_format", sa.String(length=16), server_default="12_hour", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "date_format IN ('month_day_year', 'day_month_year', 'year_month_day')",
            name="ck_system_settings_date_format",
        ),
        sa.CheckConstraint(
            "time_format IN ('12_hour', '24_hour')",
            name="ck_system_settings_time_format",
        ),
        sa.CheckConstraint("id = 1", name="ck_system_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO system_settings
            (id, timezone, date_format, time_format, created_at, updated_at)
        VALUES
            (1, 'UTC', 'month_day_year', '12_hour', now(), now())
        """
    )


def downgrade() -> None:
    """The table belongs to the preceding system-settings migration."""
    pass