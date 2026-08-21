---
name: Alembic migration heads
description: How to keep deployment migrations valid when separate work produces sibling Alembic revisions.
---

When independent migrations share a parent revision, add a no-op merge revision that depends on both before delivery so the project has one canonical Alembic head.

**Why:** A post-merge helper can upgrade all heads, but standard deployment commands and release validation expect `alembic upgrade head` to resolve to one target.

**How to apply:** After task merges that add migrations, run `alembic heads`. If more than one head exists, create a merge revision, then verify both `alembic upgrade head` and `alembic upgrade head --sql`. If reconciliation changes revision ancestry after development has already been stamped, verify the required tables exist too; add a non-destructive repair migration when the version table is ahead of the actual schema.