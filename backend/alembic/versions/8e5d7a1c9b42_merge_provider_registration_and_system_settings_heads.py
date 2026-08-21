"""merge provider registration and system settings heads

Revision ID: 8e5d7a1c9b42
Revises: 4ac129e5b673, c0f812de4b11
"""
from typing import Sequence, Union


revision: str = "8e5d7a1c9b42"
down_revision: Union[str, Sequence[str], None] = (
    "4ac129e5b673",
    "c0f812de4b11",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join concurrent feature branches without additional schema changes."""


def downgrade() -> None:
    """Split the migration graph without reverting either feature branch."""