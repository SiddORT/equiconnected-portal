"""add provider portal setup pending state

Revision ID: ab39f780e1d2
Revises: f2985f8a52ee
"""
from alembic import op
import sqlalchemy as sa


revision = "ab39f780e1d2"
down_revision = "f2985f8a52ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "provider_portal_setup_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "provider_portal_setup_pending")