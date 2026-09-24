"""add doctor availability and independent dated visit locations

Revision ID: e8a0f1d37246
Revises: c2d4e6f8a901
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "e8a0f1d37246"
down_revision = "c2d4e6f8a901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    availability = sa.Enum("ONGOING", "VISITING", name="doctor_availability")
    availability.create(op.get_bind(), checkfirst=True)
    op.add_column("providers", sa.Column("doctor_availability", availability, nullable=True))
    op.create_table(
        "doctor_visits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location", JSONB, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("start_date <= end_date", name="ck_doctor_visits_date_order"),
    )
    op.create_index("ix_doctor_visits_provider_dates", "doctor_visits", ["provider_id", "start_date", "end_date"])


def downgrade() -> None:
    op.drop_index("ix_doctor_visits_provider_dates", table_name="doctor_visits")
    op.drop_table("doctor_visits")
    op.drop_column("providers", "doctor_availability")
    sa.Enum(name="doctor_availability").drop(op.get_bind(), checkfirst=True)