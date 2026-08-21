"""add provider registration applications

Revision ID: 4ac129e5b673
Revises: b35196334e9b
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "4ac129e5b673"
down_revision = "b35196334e9b"
branch_labels = None
depends_on = None


application_status = postgresql.ENUM(
    "AWAITING_EMAIL_VERIFICATION",
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    name="provider_application_status",
    create_type=False,
)
provider_type = postgresql.ENUM(
    "HOSPITAL",
    "CLINIC",
    "DOCTOR",
    name="provider_type",
    create_type=False,
)
visit_stability = postgresql.ENUM(
    "STABLE_VISIT",
    "NOT_STABLE_VISIT",
    name="visit_stability",
    create_type=False,
)


def upgrade() -> None:
    application_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "provider_registration_applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=True),
        sa.Column(
            "provider_type",
            provider_type,
            nullable=False,
        ),
        sa.Column("provider_name", sa.String(length=300), nullable=False),
        sa.Column(
            "visit_stability",
            visit_stability,
            nullable=False,
        ),
        sa.Column(
            "review_status",
            application_status,
            nullable=False,
            server_default="AWAITING_EMAIL_VERIFICATION",
        ),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_provider_registration_applications_review_status",
        "provider_registration_applications",
        ["review_status", "created_at"],
    )
    op.create_index(
        "ix_provider_registration_applications_provider_type",
        "provider_registration_applications",
        ["provider_type"],
    )
    op.execute(
        """
        INSERT INTO roles (name, description, created_at, updated_at)
        VALUES ('provider', 'Provider account application', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_registration_applications_provider_type",
        table_name="provider_registration_applications",
    )
    op.drop_index(
        "ix_provider_registration_applications_review_status",
        table_name="provider_registration_applications",
    )
    op.drop_table("provider_registration_applications")
    application_status.drop(op.get_bind(), checkfirst=True)