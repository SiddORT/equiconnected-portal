"""add email delivery logs

Revision ID: c9baea2f15e7
Revises: a4f68b20de91
Create Date: 2026-08-21 10:47:09.903163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9baea2f15e7'
down_revision: Union[str, None] = 'a4f68b20de91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('email_delivery_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('recipient_email', sa.String(length=255), nullable=False),
    sa.Column('purpose', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('failure_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("purpose IN ('provider_invitation', 'account_verification')", name='ck_email_delivery_logs_purpose'),
    sa.CheckConstraint("status IN ('pending', 'success', 'failed')", name='ck_email_delivery_logs_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_delivery_logs_created_at_id', 'email_delivery_logs', ['created_at', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_delivery_logs_created_at_id', table_name='email_delivery_logs')
    op.drop_table('email_delivery_logs')
