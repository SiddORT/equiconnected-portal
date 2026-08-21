"""add public subscribers and confirmation email purpose

Revision ID: 9b6e2a1f4c77
Revises: 24dd1afe85b3
"""
from alembic import op
import sqlalchemy as sa


revision: str = "9b6e2a1f4c77"
down_revision: str | None = "24dd1afe85b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'subscriber_confirmation')",
    )
    op.create_table(
        "subscribers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("registration_type", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "registration_type IN "
            "('VET', 'HORSE_OWNER', 'HOSPITAL', 'CLINIC', 'STABLE_MANAGER', 'OTHER')",
            name="ck_subscribers_registration_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_subscribers_email"),
    )
    op.create_index(
        "ix_subscribers_submitted_at_id",
        "subscribers",
        ["submitted_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_subscribers_registration_type_submitted_at",
        "subscribers",
        ["registration_type", "submitted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscribers_registration_type_submitted_at",
        table_name="subscribers",
    )
    op.drop_index("ix_subscribers_submitted_at_id", table_name="subscribers")
    op.drop_table("subscribers")
    op.drop_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', 'provider_portal_access')",
    )