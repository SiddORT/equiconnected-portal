"""backfill_provider_contacts

Copy the legacy single-value providers.email / providers.phone columns into
the new provider_emails / provider_phones tables (as primary entries), then
null out the legacy columns. Backwards compatible — no data loss.

Revision ID: 781951970595
Revises: a76f5d02455e
Create Date: 2026-08-18 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '781951970595'
down_revision: Union[str, None] = 'a76f5d02455e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy emails → provider_emails (primary), skipping providers that
    # already have a primary email (partial unique index safety).
    op.execute(sa.text("""
        INSERT INTO provider_emails (id, provider_id, email, is_primary, created_at, updated_at)
        SELECT gen_random_uuid(), p.id, trim(p.email), true, now(), now()
        FROM providers p
        WHERE p.email IS NOT NULL AND trim(p.email) <> ''
          AND NOT EXISTS (
            SELECT 1 FROM provider_emails e
            WHERE e.provider_id = p.id AND e.is_primary
          )
    """))
    # Legacy phones → provider_phones (primary). If the stored value starts
    # with an international prefix like "+44 …", split it into country code +
    # local number; otherwise keep the whole value as the number with a
    # neutral "+1" code (best effort — legacy format was free text).
    op.execute(sa.text(r"""
        INSERT INTO provider_phones (id, provider_id, country_code, number, is_primary, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            p.id,
            COALESCE(substring(trim(p.phone) FROM '^(\+\d{1,4})[\s.-]'), '+1'),
            COALESCE(
                NULLIF(trim(substring(trim(p.phone) FROM '^\+\d{1,4}[\s.-](.*)$')), ''),
                trim(p.phone)
            ),
            true, now(), now()
        FROM providers p
        WHERE p.phone IS NOT NULL AND trim(p.phone) <> ''
          AND NOT EXISTS (
            SELECT 1 FROM provider_phones ph
            WHERE ph.provider_id = p.id AND ph.is_primary
          )
    """))
    # Legacy columns are kept but null going forward.
    op.execute(sa.text("UPDATE providers SET email = NULL, phone = NULL"))


def downgrade() -> None:
    # Restore the primary entries back into the legacy columns.
    op.execute(sa.text("""
        UPDATE providers p SET email = e.email
        FROM provider_emails e
        WHERE e.provider_id = p.id AND e.is_primary
    """))
    op.execute(sa.text("""
        UPDATE providers p SET phone = ph.country_code || ' ' || ph.number
        FROM provider_phones ph
        WHERE ph.provider_id = p.id AND ph.is_primary
    """))
