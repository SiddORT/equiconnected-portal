---
name: PostgreSQL locking with eager relationships
description: Avoid PostgreSQL row-lock errors caused by optional joined relationships.
---

When locking a root record that has optional eagerly loaded relationships, scope the lock to the root table rather than issuing an unqualified `FOR UPDATE`.

**Why:** PostgreSQL rejects an unqualified row lock when the ORM query includes an outer join, because it would try to lock the nullable side of that join. The root-row lock still serializes state transitions while preserving eager-loaded response data.

**How to apply:** For decision flows that load an optional linked record, use a table-scoped `FOR UPDATE OF <root table>` and add a real multi-session regression test for competing decisions.