"""add privacy-minimal daily analytics traffic aggregates

Revision ID: e3b5a49c1d72
Revises: 41bd7a693e20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e3b5a49c1d72"
down_revision: Union[str, None] = "41bd7a693e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_traffic_page_category_daily",
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("page_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "page_views >= 0", name="ck_analytics_traffic_category_nonnegative"
        ),
        sa.CheckConstraint(
            "category IN ('home', 'animation', 'signup', 'provider_signup', 'terms', "
            "'privacy', 'provider_directory', 'provider_profile')",
            name="ck_analytics_traffic_category_allowed",
        ),
        sa.PrimaryKeyConstraint("visit_date", "category"),
    )
    op.create_index(
        "ix_analytics_traffic_category_date",
        "analytics_traffic_page_category_daily",
        ["category", "visit_date"],
    )

    op.create_table(
        "analytics_traffic_provider_profile_daily",
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "profile_views >= 0", name="ck_analytics_traffic_provider_nonnegative"
        ),
        sa.PrimaryKeyConstraint("visit_date", "provider_id"),
    )
    op.create_index(
        "ix_analytics_traffic_provider_date",
        "analytics_traffic_provider_profile_daily",
        ["provider_id", "visit_date"],
    )

    op.create_table(
        "analytics_traffic_visitor_daily",
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("estimated_visitors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estimated_visitors >= 0",
            name="ck_analytics_traffic_visitors_nonnegative",
        ),
        sa.PrimaryKeyConstraint("visit_date"),
    )

    op.create_table(
        "analytics_traffic_tracking_metadata",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("tracking_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id = 1", name="ck_analytics_traffic_metadata_singleton"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO analytics_traffic_tracking_metadata "
            "(id, tracking_started_at) VALUES (1, CURRENT_TIMESTAMP)"
        )
    )

    op.create_table(
        "analytics_traffic_tracking_receipts",
        sa.Column("navigation_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("navigation_key"),
    )
    op.create_index(
        "ix_analytics_traffic_receipts_expiry",
        "analytics_traffic_tracking_receipts",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analytics_traffic_receipts_expiry",
        table_name="analytics_traffic_tracking_receipts",
    )
    op.drop_table("analytics_traffic_tracking_receipts")
    op.drop_table("analytics_traffic_tracking_metadata")
    op.drop_table("analytics_traffic_visitor_daily")
    op.drop_index(
        "ix_analytics_traffic_provider_date",
        table_name="analytics_traffic_provider_profile_daily",
    )
    op.drop_table("analytics_traffic_provider_profile_daily")
    op.drop_index(
        "ix_analytics_traffic_category_date",
        table_name="analytics_traffic_page_category_daily",
    )
    op.drop_table("analytics_traffic_page_category_daily")