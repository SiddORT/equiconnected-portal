"""add organization requests

Revision ID: b91a6148f20d
Revises: a1523b656e74
"""
from alembic import op

revision = "b91a6148f20d"
down_revision = "a1523b656e74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organization_request_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        CREATE TABLE organization_requests (
            id UUID PRIMARY KEY,
            doctor_provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
            organization_name VARCHAR(300) NOT NULL,
            organization_type provider_type NOT NULL,
            contact_email VARCHAR(254),
            location_hint VARCHAR(500),
            status organization_request_status NOT NULL DEFAULT 'PENDING',
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT ck_organization_request_type CHECK (organization_type IN ('HOSPITAL', 'CLINIC'))
        )
    """)
    op.execute("CREATE INDEX ix_organization_requests_doctor_provider_id ON organization_requests (doctor_provider_id)")
    op.execute("CREATE INDEX ix_organization_requests_status ON organization_requests (status)")
    op.execute("CREATE INDEX ix_organization_requests_organization_type ON organization_requests (organization_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organization_requests")
    op.execute("DROP TYPE IF EXISTS organization_request_status")