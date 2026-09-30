"""Add explicit direct-listing portal ownership and setup token route.

Revision ID: b27a8419c355
Revises: aa37bc91e204
"""
from alembic import op
import sqlalchemy as sa

revision = "b27a8419c355"
down_revision = "aa37bc91e204"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "direct_provider_portal_access",
        sa.Column("provider_id", sa.UUID(), sa.ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.alter_column("provider_portal_setup_tokens", "invitation_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("provider_portal_setup_tokens", sa.Column(
        "direct_provider_id", sa.UUID(), sa.ForeignKey("direct_provider_portal_access.provider_id", ondelete="CASCADE")
    ))
    op.create_index("ix_provider_portal_setup_tokens_direct_provider_id", "provider_portal_setup_tokens", ["direct_provider_id"])
    op.create_check_constraint(
        "ck_provider_setup_token_owner", "provider_portal_setup_tokens",
        "(invitation_id IS NOT NULL) <> (direct_provider_id IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("ck_provider_setup_token_owner", "provider_portal_setup_tokens", type_="check")
    op.drop_index("ix_provider_portal_setup_tokens_direct_provider_id", table_name="provider_portal_setup_tokens")
    op.drop_column("provider_portal_setup_tokens", "direct_provider_id")
    op.alter_column("provider_portal_setup_tokens", "invitation_id", existing_type=sa.UUID(), nullable=False)
    op.drop_table("direct_provider_portal_access")