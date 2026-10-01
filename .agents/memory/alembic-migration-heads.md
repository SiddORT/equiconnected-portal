---
name: Alembic migration heads
description: How to keep deployment migrations valid when separate work produces sibling Alembic revisions.
---

When independent migrations share a parent revision, add a merge revision that depends on both before delivery so the project has one canonical Alembic head.

**Why:** A post-merge helper can upgrade all heads, but standard deployment commands and release validation expect `alembic upgrade head` to resolve to one target.

If sibling migrations both replace the same constraint, reconcile their combined allowed values in the merge revision rather than making it a no-op.

**Why:** Head reconciliation alone does not reconcile schema semantics. A later-running sibling can silently remove the earlier branch's allowed email purposes even though both feature tables exist.

Each sibling upgrade must also preserve the other branch's accepted values before recreating the constraint; fixing only the merge revision is too late.

**Why:** A populated parent branch can already have rows carrying its new values. PostgreSQL validates replacement constraints immediately, so an intermediate constraint excluding those rows aborts before the merge runs.

**How to apply:** After task merges that add migrations, run `alembic heads`. If more than one head exists, create a merge revision, then verify both `alembic upgrade head` and `alembic upgrade head --sql`. For overlapping constraints, test both branch application orders with populated histories, verify every row is preserved, and verify the merged union. If reconciliation changes revision ancestry after development has already been stamped, verify the required tables exist too; add a non-destructive repair migration when the version table is ahead of the actual schema.

A revision reported by an external database is not necessarily a known branch head in the repository. Recover the original migration and its ancestry before using it as a merge parent.

**Why:** A merge referencing an absent revision makes Alembic's graph invalid. Inventing a placeholder parent or stamping the database conceals unknown schema operations instead of repairing their history.

**How to apply:** Check local heads, the remote branch, and available Git history. If the revision remains absent, request its original migration file from the operator; do not guess its parent, replace existing migrations, or claim a two-head merge is verified.