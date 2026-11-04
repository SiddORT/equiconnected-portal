"""Add the public horse rider role without changing existing accounts."""
from alembic import op
import sqlalchemy as sa

revision = "7d42b1e9a603"
down_revision = "8828d27aea34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO roles (name, description, created_at, updated_at)
        VALUES ('horse_rider', 'Public horse rider account', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (name) DO NOTHING
    """))


def downgrade() -> None:
    used = op.get_bind().execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM users JOIN roles ON roles.id = users.role_id
            WHERE roles.name = 'horse_rider'
            UNION ALL
            SELECT 1 FROM user_roles JOIN roles ON roles.id = user_roles.role_id
            WHERE roles.name = 'horse_rider'
        )
    """)).scalar()
    if used:
        raise RuntimeError("Cannot remove horse_rider while accounts use it; review those accounts before downgrading.")
    op.execute(sa.text("DELETE FROM roles WHERE name = 'horse_rider'"))
