---
name: PostgreSQL test-schema isolation
description: Keep pytest cleanup confined to its dedicated PostgreSQL schema.
---

When a test database uses `SET search_path` to isolate a schema, commit that
session setting during connection setup before the connection enters
SQLAlchemy's pool.

**Why:** PostgreSQL starts an implicit transaction for the setting; a pool
rollback can undo an uncommitted setting and leave cleanup statements targeting
the default development schema.

**How to apply:** Any new test engine that selects a dedicated schema must make
the selection durable for the connection before test setup, inserts, or cleanup
run. Verify with a public-data preservation check after changing the fixture.