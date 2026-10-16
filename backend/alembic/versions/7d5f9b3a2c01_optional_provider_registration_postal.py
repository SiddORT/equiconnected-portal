"""Allow provider applications without a postal code.

Revision ID: 7d5f9b3a2c01
Revises: 6c4e8a2f1b90
"""
from alembic import op
import sqlalchemy as sa

revision = "7d5f9b3a2c01"
down_revision = "6c4e8a2f1b90"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("provider_registration_applications", "postal_code",
                    existing_type=sa.String(32), nullable=True)


def downgrade():
    # Refuse a downgrade with nulls rather than fabricate historical codes.
    op.alter_column("provider_registration_applications", "postal_code",
                    existing_type=sa.String(32), nullable=False)
