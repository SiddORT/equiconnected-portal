"""add provider invitations

Revision ID: a1523b656e74
Revises: d1e9102efbc7
Create Date: 2026-08-19 05:03:22.704913

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1523b656e74'
down_revision: Union[str, None] = 'd1e9102efbc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing native enums are extended in place. Existing rows remain valid.
    op.execute("ALTER TYPE provider_status ADD VALUE IF NOT EXISTS 'DRAFT'")
    op.execute("ALTER TYPE provider_status ADD VALUE IF NOT EXISTS 'UNDER_REVIEW'")
    op.execute("ALTER TYPE doctor_organization_status ADD VALUE IF NOT EXISTS 'PENDING'")
    op.execute("ALTER TYPE doctor_organization_status ADD VALUE IF NOT EXISTS 'REJECTED'")
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invitation_status AS ENUM
                ('PENDING', 'ACCEPTED', 'EXPIRED', 'CANCELLED', 'COMPLETED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    # Raw SQL prevents SQLAlchemy from trying to recreate the existing provider_type enum.
    op.execute("""
        CREATE TABLE provider_invitations (
            id UUID PRIMARY KEY,
            provider_id UUID REFERENCES providers(id) ON DELETE SET NULL,
            provider_type provider_type NOT NULL,
            recipient_email VARCHAR(254) NOT NULL,
            token_hash VARCHAR(64) NOT NULL,
            status invitation_status NOT NULL DEFAULT 'PENDING',
            expires_at TIMESTAMPTZ NOT NULL,
            sent_at TIMESTAMPTZ NOT NULL,
            accepted_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX ix_provider_invitations_expires_at ON provider_invitations (expires_at)")
    op.execute("CREATE INDEX ix_provider_invitations_provider_email ON provider_invitations (provider_id, recipient_email)")
    op.execute("""
        CREATE UNIQUE INDEX uq_provider_invitations_active_provider_email
            ON provider_invitations (provider_id, recipient_email)
            WHERE status IN ('PENDING', 'ACCEPTED')
    """)
    op.execute("CREATE INDEX ix_provider_invitations_status ON provider_invitations (status)")
    op.execute("CREATE UNIQUE INDEX ix_provider_invitations_token_hash ON provider_invitations (token_hash)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS provider_invitations")
    op.execute("DROP TYPE IF EXISTS invitation_status")
    # PostgreSQL cannot safely remove enum values while dependent columns exist.
    # DRAFT/UNDER_REVIEW and PENDING/REJECTED intentionally remain available.
