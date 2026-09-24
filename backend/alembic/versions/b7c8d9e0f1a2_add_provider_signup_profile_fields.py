"""add provider signup profile and capability fields

Revision ID: b7c8d9e0f1a2
Revises: 9b6e2a1f4c77
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7c8d9e0f1a2"
down_revision = "9b6e2a1f4c77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provider_registration_applications", sa.Column("professional_title", sa.String(200), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("specialization_ids", postgresql.ARRAY(sa.UUID()), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("working_address", sa.String(500), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("stable_visit", sa.Boolean(), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("clinic_hospital_visit", sa.Boolean(), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("maximum_working_radius_km", sa.Numeric(10, 2), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("emergency_services_available", sa.Boolean(), nullable=True))
    op.add_column("provider_registration_applications", sa.Column("emergency_contact_number", sa.String(50), nullable=True))
    op.add_column("providers", sa.Column("professional_title", sa.String(200), nullable=True))
    op.add_column("providers", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("clinic_hospital_visit", sa.Boolean(), nullable=True))
    op.add_column("providers", sa.Column("maximum_working_radius_km", sa.Numeric(10, 2), nullable=True))
    op.add_column("providers", sa.Column("emergency_services_available", sa.Boolean(), nullable=True))
    op.add_column("providers", sa.Column("emergency_contact_number", sa.String(50), nullable=True))


def downgrade() -> None:
    for name in ("emergency_contact_number", "emergency_services_available", "maximum_working_radius_km", "clinic_hospital_visit", "years_experience", "professional_title"):
        op.drop_column("providers", name)
    for name in ("emergency_contact_number", "emergency_services_available", "maximum_working_radius_km", "clinic_hospital_visit", "stable_visit", "working_address", "years_experience", "specialization_ids", "professional_title"):
        op.drop_column("provider_registration_applications", name)