"""add admin provider emergency and doctor name fields

Revision ID: c2d4e6f8a901
Revises: 9a1f2c3d4e5f
"""
from alembic import op
import sqlalchemy as sa

revision = "c2d4e6f8a901"
down_revision = "9a1f2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("emergency_contact_name", sa.String(200), nullable=True))
    op.add_column("doctor_profiles", sa.Column("first_name", sa.String(150), nullable=True))
    op.add_column("doctor_profiles", sa.Column("last_name", sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column("doctor_profiles", "last_name")
    op.drop_column("doctor_profiles", "first_name")
    op.drop_column("providers", "emergency_contact_name")