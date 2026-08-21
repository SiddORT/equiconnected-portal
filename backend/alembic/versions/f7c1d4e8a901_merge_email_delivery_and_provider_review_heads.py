"""merge email delivery and provider review heads

Revision ID: f7c1d4e8a901
Revises: c9baea2f15e7, db4631df2e09
"""

from typing import Sequence, Union


revision: str = "f7c1d4e8a901"
down_revision: Union[str, Sequence[str], None] = ("c9baea2f15e7", "db4631df2e09")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the independent email-log and provider-review migrations."""


def downgrade() -> None:
    """Split the migration graph back into its two parent revisions."""