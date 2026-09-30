"""Backfill provider experience from legacy doctor profiles.

Revision ID: aa37bc91e204
Revises: f3c6a92e840b
"""
from alembic import op


revision = "aa37bc91e204"
down_revision = "f3c6a92e840b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE providers
        SET years_experience = doctor_profiles.years_experience
        FROM doctor_profiles
        WHERE providers.id = doctor_profiles.provider_id
          AND providers.years_experience IS NULL
          AND doctor_profiles.years_experience IS NOT NULL
        """
    )


def downgrade() -> None:
    # Data backfills are intentionally not reversed: provider years may have
    # been edited since the migration ran, so reverting could destroy data.
    pass