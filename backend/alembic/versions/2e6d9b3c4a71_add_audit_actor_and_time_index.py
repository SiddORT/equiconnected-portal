"""add audit actor type and chronological index

Revision ID: 2e6d9b3c4a71
Revises: e3f4a61bc9d2
"""
from alembic import op
import sqlalchemy as sa

revision = "2e6d9b3c4a71"
down_revision = "e3f4a61bc9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("actor_type", sa.String(length=40), nullable=False, server_default="admin"),
    )
    op.create_index(
        "ix_audit_logs_created_at_id", "audit_logs", ["created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at_id", table_name="audit_logs")
    op.drop_column("audit_logs", "actor_type")