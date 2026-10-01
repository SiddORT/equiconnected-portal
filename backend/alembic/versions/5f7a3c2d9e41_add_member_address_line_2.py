"""Add optional second address lines to member profiles."""
from alembic import op
import sqlalchemy as sa


revision = "5f7a3c2d9e41"
down_revision = "d9a4f13b7c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("address_line_2", sa.String(length=300), nullable=True))
    op.add_column("stable_profiles", sa.Column("address_line_2", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("stable_profiles", "address_line_2")
    op.drop_column("users", "address_line_2")