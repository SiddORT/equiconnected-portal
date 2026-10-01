"""Merge member-address and contact-confirmation migration heads."""
from typing import Sequence, Union


revision: str = "7bd93c4a5e61"
down_revision: Union[str, Sequence[str], None] = (
    "5f7a3c2d9e41",
    "a302c0f1d9e7",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass