"""member feedback, private browsing history, and review moderation lifecycle

Revision ID: 41bd7a693e20
Revises: 7bd93c4a5e61
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "41bd7a693e20"
down_revision: Union[str, None] = "7bd93c4a5e61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    review_status = postgresql.ENUM(
        "PENDING", "PUBLISHED", "REJECTED", "HIDDEN",
        name="provider_review_status",
    )
    review_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "provider_reviews",
        sa.Column("status", review_status, server_default="PENDING", nullable=True),
    )
    op.add_column("provider_reviews", sa.Column("member_note", sa.Text(), nullable=True))
    op.add_column("provider_reviews", sa.Column("internal_note", sa.Text(), nullable=True))
    op.add_column(
        "provider_reviews",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "provider_reviews", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        """
        UPDATE provider_reviews
        SET status = CASE
            WHEN comment_visible THEN 'PUBLISHED'::provider_review_status
            ELSE 'HIDDEN'::provider_review_status
        END
        """
    )
    op.alter_column("provider_reviews", "status", nullable=False, server_default="PENDING")
    op.drop_constraint(
        "uq_provider_reviews_provider_member", "provider_reviews", type_="unique"
    )
    op.create_index(
        "uq_provider_reviews_active_provider_member",
        "provider_reviews",
        ["provider_id", "member_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_provider_reviews_member_created",
        "provider_reviews",
        ["member_id", "created_at"],
    )
    op.create_index(
        "ix_provider_reviews_status_deleted",
        "provider_reviews",
        ["status", "deleted_at"],
    )
    op.create_check_constraint(
        "ck_provider_reviews_version", "provider_reviews", "version >= 1"
    )
    op.drop_constraint("provider_reviews_member_id_fkey", "provider_reviews", type_="foreignkey")
    op.create_foreign_key(
        "provider_reviews_member_id_fkey",
        "provider_reviews",
        "users",
        ["member_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "provider_review_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(length=200), nullable=False),
        sa.Column("actor_email", sa.String(length=254), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
            name="fk_provider_review_actions_actor_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["provider_reviews.id"], ondelete="RESTRICT",
            name="fk_provider_review_actions_review_id_provider_reviews",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_review_actions_review_created",
        "provider_review_actions",
        ["review_id", "created_at"],
    )

    op.create_table(
        "member_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitter_name", sa.String(length=200), nullable=False),
        sa.Column("submitter_email", sa.String(length=254), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="Pending", nullable=False),
        sa.Column("member_response", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('Website / App', 'Search & Matching', 'Provider Experience', "
            "'Account / Profile', 'Technical Issue', 'Suggestion', 'Other')",
            name="ck_member_feedback_category",
        ),
        sa.CheckConstraint(
            "status IN ('Pending', 'In review', 'Resolved', 'Rejected')",
            name="ck_member_feedback_status",
        ),
        sa.CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_member_feedback_rating"),
        sa.CheckConstraint("version >= 1", name="ck_member_feedback_version"),
        sa.ForeignKeyConstraint(
            ["member_id"], ["users.id"], ondelete="SET NULL",
            name="fk_member_feedback_member_id_users",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "idempotency_key", name="uq_member_feedback_member_idempotency"
        ),
    )
    op.create_index(
        "ix_member_feedback_status_submitted", "member_feedback", ["status", "submitted_at"]
    )
    op.create_index(
        "ix_member_feedback_member_submitted", "member_feedback", ["member_id", "submitted_at"]
    )

    op.create_table(
        "member_feedback_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(length=200), nullable=False),
        sa.Column("actor_email", sa.String(length=254), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
            name="fk_member_feedback_actions_actor_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["member_feedback.id"], ondelete="CASCADE",
            name="fk_member_feedback_actions_feedback_id_member_feedback",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_member_feedback_actions_feedback_created",
        "member_feedback_actions",
        ["feedback_id", "created_at"],
    )

    op.create_table(
        "member_browsing_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_name", sa.String(length=300), nullable=True),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_type IN ('search', 'provider')", name="ck_member_history_event_type"),
        sa.ForeignKeyConstraint(
            ["member_id"], ["users.id"], ondelete="CASCADE",
            name="fk_member_browsing_history_member_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["providers.id"], ondelete="SET NULL",
            name="fk_member_browsing_history_provider_id_providers",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "event_key", name="uq_member_history_member_event_key"
        ),
    )
    op.create_index(
        "ix_member_history_member_occurred",
        "member_browsing_history",
        ["member_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_member_history_member_occurred", table_name="member_browsing_history")
    op.drop_table("member_browsing_history")
    op.drop_index(
        "ix_member_feedback_actions_feedback_created", table_name="member_feedback_actions"
    )
    op.drop_table("member_feedback_actions")
    op.drop_index("ix_member_feedback_member_submitted", table_name="member_feedback")
    op.drop_index("ix_member_feedback_status_submitted", table_name="member_feedback")
    op.drop_table("member_feedback")
    op.drop_index("ix_provider_review_actions_review_created", table_name="provider_review_actions")
    op.drop_table("provider_review_actions")

    op.drop_constraint("provider_reviews_member_id_fkey", "provider_reviews", type_="foreignkey")
    op.create_foreign_key(
        "provider_reviews_member_id_fkey",
        "provider_reviews",
        "users",
        ["member_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("ck_provider_reviews_version", "provider_reviews", type_="check")
    op.drop_index("ix_provider_reviews_status_deleted", table_name="provider_reviews")
    op.drop_index("ix_provider_reviews_member_created", table_name="provider_reviews")
    op.drop_index("uq_provider_reviews_active_provider_member", table_name="provider_reviews")
    op.create_unique_constraint(
        "uq_provider_reviews_provider_member",
        "provider_reviews",
        ["provider_id", "member_id"],
    )
    op.drop_column("provider_reviews", "deleted_at")
    op.drop_column("provider_reviews", "version")
    op.drop_column("provider_reviews", "internal_note")
    op.drop_column("provider_reviews", "member_note")
    op.drop_column("provider_reviews", "status")
    postgresql.ENUM(name="provider_review_status").drop(op.get_bind(), checkfirst=True)