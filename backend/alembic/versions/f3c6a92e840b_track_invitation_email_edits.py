"""Track when an invitee has chosen their provider contact emails.

Revision ID: f3c6a92e840b
Revises: 0c3975715c3b
"""
from alembic import op
import sqlalchemy as sa

revision = "f3c6a92e840b"
down_revision = "0c3975715c3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_invitations",
        sa.Column("emails_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("provider_invitations", "emails_edited")