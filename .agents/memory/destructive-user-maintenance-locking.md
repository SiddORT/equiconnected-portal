---
name: Destructive user maintenance locking
description: Transaction boundary required for maintenance actions that retain users by administrative role.
---

# Destructive user maintenance locking

When a destructive maintenance command retains accounts based on their roles,
calculate the retained/deleted scope only after taking a transaction-scoped
PostgreSQL lock over users, role assignments, roles, and restrictive
user-reference tables.

**Why:** Admin authorization is represented both by a primary role and a
relational role assignment. Row locks on users alone allow concurrent role
changes to invalidate the last-active-admin safety check, and concurrent
invitation creation can invalidate restrictive-reference preflight.

**How to apply:** Keep the scope calculation, active-admin validation,
restrictive-reference preflight, and delete in one transaction while the
maintenance locks are held. Treat a separately printed dry run as an audit
aid; a confirmed operation must always calculate its own current scope.