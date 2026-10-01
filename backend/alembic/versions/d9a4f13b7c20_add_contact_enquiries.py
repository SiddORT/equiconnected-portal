"""Persist public contact enquiries and account for notifications.

Revision ID: d9a4f13b7c20
Revises: b27a8419c355
"""
from alembic import op
import sqlalchemy as sa


revision: str = "d9a4f13b7c20"
down_revision: str | None = "b27a8419c355"
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
        "'provider_portal_access', 'subscriber_confirmation', "
        "'smtp_test', 'contact_notification')",
    )
    op.create_table(
        "contact_enquiries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("enquiry_type", sa.String(length=30), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "enquiry_type IN ('general', 'listing', 'partnership', 'other')",
            name="ck_contact_enquiries_enquiry_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contact_enquiries_submitted_at_id",
        "contact_enquiries",
        ["submitted_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_contact_enquiries_enquiry_type_submitted_at",
        "contact_enquiries",
        ["enquiry_type", "submitted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contact_enquiries_enquiry_type_submitted_at",
        table_name="contact_enquiries",
    )
    op.drop_index(
        "ix_contact_enquiries_submitted_at_id",
        table_name="contact_enquiries",
    )
    op.drop_table("contact_enquiries")
    op.drop_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        type_="check",
    )
    # Existing contact notification history prevents this downgrade; preserve
    # audit history rather than deleting it to force a rollback.
    op.create_check_constraint(
        "ck_email_delivery_logs_purpose",
        "email_delivery_logs",
        "purpose IN ('provider_invitation', 'account_verification', "
        "'provider_portal_access', 'subscriber_confirmation', 'smtp_test')",
    )