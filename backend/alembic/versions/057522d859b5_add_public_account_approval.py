"""add public account approval

Revision ID: 057522d859b5
Revises: 08e5eba54f96
Create Date: 2026-08-21 07:19:25.286700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '057522d859b5'
down_revision: Union[str, None] = '08e5eba54f96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    approval_status = sa.Enum(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="public_account_approval_status",
    )
    approval_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users", sa.Column("approval_status", approval_status, nullable=True)
    )
    op.add_column(
        "users", sa.Column("approval_decided_at", sa.DateTime(timezone=True), nullable=True)
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
    # Keep the approval stage explicit for every existing public registration.
    # Existing administrators are deliberately excluded and keep a NULL state.
    op.execute(
        """
        UPDATE users
        SET approval_status = 'PENDING'
        WHERE id IN (
            SELECT user_roles.user_id
            FROM user_roles
            JOIN roles ON roles.id = user_roles.role_id
            WHERE roles.name IN ('horse_owner', 'stable_manager')
        )
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_approval_decided_by", "users", type_="foreignkey")
    op.drop_index("ix_users_approval_decided_by", table_name="users")
    op.drop_column("users", "approval_decided_by")
    op.drop_column("users", "approval_decided_at")
    op.drop_column("users", "approval_status")
    sa.Enum(name="public_account_approval_status").drop(
        op.get_bind(), checkfirst=True
    )
