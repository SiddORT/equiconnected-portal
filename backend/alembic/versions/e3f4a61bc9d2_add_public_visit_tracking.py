"""add public visit tracking

Revision ID: e3f4a61bc9d2
Revises: b91a6148f20d
"""
import sqlalchemy as sa
from alembic import op

revision = "e3f4a61bc9d2"
down_revision = "b91a6148f20d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_visit_daily",
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("visit_count >= 0", name="ck_public_visit_daily_nonnegative"),
        sa.PrimaryKeyConstraint("visit_date"),
    )


def downgrade() -> None:
    op.drop_table("public_visit_daily")