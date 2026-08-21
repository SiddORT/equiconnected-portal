"""remove public account approval

Revision ID: a4f68b20de91
Revises: 386effdd71c4
Create Date: 2026-08-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4f68b20de91"
down_revision: Union[str, None] = "386effdd71c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_users_approval_decided_by", "users", type_="foreignkey")
    op.drop_index("ix_users_approval_decided_by", table_name="users")
    op.drop_column("users", "approval_decided_by")
    op.drop_column("users", "approval_decided_at")
    op.drop_column("users", "approval_status")
    sa.Enum(name="public_account_approval_status").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    approval_status = sa.Enum(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="public_account_approval_status",
    )
    approval_status.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("approval_status", approval_status, nullable=True))
    op.add_column(
        "users",
        sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("approval_decided_by", sa.UUID(), nullable=True))
    op.create_index(
        "ix_users_approval_decided_by",
        "users",
        ["approval_decided_by"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_approval_decided_by",
        "users",
        "users",
        ["approval_decided_by"],
        ["id"],
        ondelete="SET NULL",
    )