---
name: Password recovery session locking
description: Why recovery and session issuance need one shared account serialization boundary.
---

Password recovery, password sign-in, and refresh rotation must serialize on the same account before checking credentials or creating/revoking refresh sessions, and then lock token rows in that order.

**Why:** Revoking all existing refresh sessions is insufficient if a concurrent sign-in already verified the old password and commits a new session after the reset. Refresh rotation has the same race. Cached ORM account/token objects must be refreshed after acquiring the lock.

**How to apply:** Preserve this account-first ordering in every future password/session issuance change. Access JWT expiry remains a separate policy; refresh-session revocation does not promise immediate access-token invalidation.