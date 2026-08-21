"""merge activity and registration heads

Revision ID: c8e1f3a6b924
Revises: 2e6d9b3c4a71, f2a8d0c7314b
"""


revision = "c8e1f3a6b924"
down_revision = ("2e6d9b3c4a71", "f2a8d0c7314b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join independent activity-log and registration migrations."""


def downgrade() -> None:
    """Split the migration graph back to its two parent revisions."""