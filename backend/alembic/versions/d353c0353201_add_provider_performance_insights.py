"""add privacy-minimal provider contact insight aggregates

Revision ID: d353c0353201
Revises: 4f8a2c1d6e90
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d353c0353201"
down_revision: Union[str, None] = "4f8a2c1d6e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_contact_click_daily",
        sa.Column("click_date", sa.Date(), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "click_count >= 0", name="ck_provider_contact_click_count"
        ),
        sa.CheckConstraint(
            "action IN ('phone', 'email', 'website')",
            name="ck_provider_contact_click_action",
        ),
        sa.PrimaryKeyConstraint("click_date", "provider_id", "action"),
    )
    op.create_index(
        "ix_provider_contact_click_provider_date",
        "provider_contact_click_daily",
        ["provider_id", "click_date"],
    )

    op.create_table(
        "provider_contact_click_tracking_metadata",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("tracking_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id = 1", name="ck_provider_contact_tracking_singleton"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO provider_contact_click_tracking_metadata "
            "(id, tracking_started_at) VALUES (1, CURRENT_TIMESTAMP)"
        )
    )

    # Conversation rows existed before provider insights. This is an explicit
    # reporting rollout boundary; never infer it from a surviving conversation.
    op.create_table(
        "provider_insights_conversation_metadata",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("tracking_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id = 1", name="ck_provider_insights_conversation_singleton"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO provider_insights_conversation_metadata "
            "(id, tracking_started_at) VALUES (1, CURRENT_TIMESTAMP)"
        )
    )

    op.create_table(
        "provider_contact_click_receipts",
        sa.Column("event_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_key"),
    )
    op.create_index(
        "ix_provider_contact_click_receipts_expiry",
        "provider_contact_click_receipts",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_contact_click_receipts_expiry",
        table_name="provider_contact_click_receipts",
    )
    op.drop_table("provider_contact_click_receipts")
    op.drop_table("provider_insights_conversation_metadata")
    op.drop_table("provider_contact_click_tracking_metadata")
    op.drop_index(
        "ix_provider_contact_click_provider_date",
        table_name="provider_contact_click_daily",
    )
    op.drop_table("provider_contact_click_daily")