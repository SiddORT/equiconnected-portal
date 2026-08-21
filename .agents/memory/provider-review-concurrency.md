---
name: Provider review concurrency
description: Ensures one member review per provider remains an idempotent write under simultaneous submissions.
---

Member review submission must be implemented as an atomic database upsert keyed by provider and member.

**Why:** A read-then-insert permits two first-time submissions to observe no existing record. The unique constraint protects data integrity, but the losing request fails unless the write is conflict-safe.

**How to apply:** Keep the database uniqueness constraint and use a conflict-aware insert/update whenever review submission behavior is changed. Preserve comment visibility when a member edits a review so moderation cannot be bypassed by an update.