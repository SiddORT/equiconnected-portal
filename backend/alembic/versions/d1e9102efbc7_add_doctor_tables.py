"""add_doctor_tables

Revision ID: d1e9102efbc7
Revises: d8912e12cf71
Create Date: 2026-08-19 04:45:18.869668

Uses raw SQL throughout to avoid SQLAlchemy ORM auto-emitting CREATE TYPE
for enum columns when the model metadata is loaded.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd1e9102efbc7'
down_revision: Union[str, None] = 'd8912e12cf71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE doctor_organization_status AS ENUM ('ACTIVE', 'INACTIVE');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS doctor_profiles (
            provider_id     UUID        PRIMARY KEY
                                        REFERENCES providers(id) ON DELETE CASCADE,
            professional_title VARCHAR(200),
            biography       TEXT,
            years_experience INTEGER,
            experience_description TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS doctor_qualifications (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_id     UUID        NOT NULL
                                        REFERENCES providers(id) ON DELETE CASCADE,
            title           VARCHAR(300) NOT NULL,
            institution     VARCHAR(300),
            year_obtained   INTEGER,
            description     TEXT,
            display_order   INTEGER     NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_doctor_qualifications_provider_id
            ON doctor_qualifications (provider_id)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS doctor_organizations (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            doctor_id       UUID        NOT NULL
                                        REFERENCES providers(id) ON DELETE CASCADE,
            organization_id UUID        NOT NULL
                                        REFERENCES providers(id) ON DELETE CASCADE,
            status          doctor_organization_status NOT NULL DEFAULT 'ACTIVE',
            is_primary      BOOLEAN     NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_doctor_organizations_pair UNIQUE (doctor_id, organization_id),
            CONSTRAINT ck_doctor_org_no_self CHECK (doctor_id != organization_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_doctor_organizations_doctor_id
            ON doctor_organizations (doctor_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_doctor_organizations_organization_id
            ON doctor_organizations (organization_id)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_organizations_one_primary
            ON doctor_organizations (doctor_id)
            WHERE is_primary = true
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS doctor_organizations")
    op.execute("DROP TABLE IF EXISTS doctor_qualifications")
    op.execute("DROP TABLE IF EXISTS doctor_profiles")
    op.execute("DROP TYPE IF EXISTS doctor_organization_status")
