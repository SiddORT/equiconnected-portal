---
name: Missing Alembic version history
description: Safe response when a populated development database has no recorded Alembic revision.
---

If Alembic reports no current revision while the application tables already exist, treat it as missing migration history, not a fresh database. Do not drop tables or add automatic stamping to post-merge setup.

**Why:** Post-merge migration attempted the initial schema against an existing populated database and failed on a duplicate table. Blindly stamping could conceal genuinely unapplied schema changes.

**How to apply:** Inspect table coverage and the objects from the latest migrations, then repair only the development database's revision metadata if those checks establish that the schema is already current. Retry the full post-merge setup afterward.