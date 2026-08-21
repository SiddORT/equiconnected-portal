"""restore public registration roles

Revision ID: d4b7e9a1c203
Revises: 057522d859b5
"""
from alembic import op


revision = "d4b7e9a1c203"
down_revision = "057522d859b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Restore required public roles without touching existing assignments."""
    op.execute(
        """
        INSERT INTO roles (name, description, created_at, updated_at)
        VALUES
            ('horse_owner', 'Public horse owner account', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('stable_manager', 'Public stable manager account', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    """Keep repaired roles in place; removing them could affect existing accounts."""