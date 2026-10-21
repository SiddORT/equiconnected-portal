"""Retain legacy proposals explicitly saved by their owner, without admin approval.

Revision ID: 8e6a1d4b2c90
Revises: 7d5f9b3a2c01
"""
from alembic import op
import sqlalchemy as sa

revision = "8e6a1d4b2c90"
down_revision = "7d5f9b3a2c01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE provider_profile_update_status ADD VALUE IF NOT EXISTS 'SAVED_DIRECTLY'")


def downgrade():
    # Never reclassify an owner's save as an administrator approval.
    bind = op.get_bind()
    if bind.scalar(sa.text(
        "SELECT count(*) FROM provider_profile_updates "
        "WHERE review_status::text = 'SAVED_DIRECTLY'"
    )):
        raise RuntimeError("Cannot downgrade while owner-saved profile history exists.")
    op.execute("ALTER TABLE provider_profile_updates ALTER COLUMN review_status DROP DEFAULT")
    op.execute("ALTER TYPE provider_profile_update_status RENAME TO provider_profile_update_status_old")
    op.execute("CREATE TYPE provider_profile_update_status AS ENUM ('PENDING_REVIEW', 'APPROVED', 'REJECTED')")
    op.execute(
        "ALTER TABLE provider_profile_updates ALTER COLUMN review_status "
        "TYPE provider_profile_update_status USING review_status::text::provider_profile_update_status"
    )
    op.execute("ALTER TABLE provider_profile_updates ALTER COLUMN review_status SET DEFAULT 'PENDING_REVIEW'")
    op.execute("DROP TYPE provider_profile_update_status_old")
