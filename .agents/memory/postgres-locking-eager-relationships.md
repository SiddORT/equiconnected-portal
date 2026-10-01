---
name: PostgreSQL locking with eager relationships
description: Avoid PostgreSQL row-lock errors caused by optional joined relationships.
---

When locking a root record that has optional eagerly loaded relationships, scope the lock to the root table rather than issuing an unqualified `FOR UPDATE`.

**Why:** PostgreSQL rejects an unqualified row lock when the ORM query includes an outer join, because it would try to lock the nullable side of that join. The root-row lock still serializes state transitions while preserving eager-loaded response data.

**How to apply:** For decision flows that load an optional linked record, use a table-scoped `FOR UPDATE OF <root table>` and add a real multi-session regression test for competing decisions.

A root-row lock does not refresh objects or relationship collections already in SQLAlchemy's identity map. Re-read scheduling and eligibility state after acquiring the lock, explicitly refreshing previously loaded rows.

**Why:** A request can read a listing before waiting for another writer's lock; once that writer commits, a cached collection can still omit its newly saved trip or retain outdated trip dates. Lock serialization alone therefore does not make overlap validation current.

**How to apply:** Validate against fresh schedule queries under the provider-root lock, not a relationship loaded before the lock. Exercise approval against an administrator schedule write using independent database sessions.