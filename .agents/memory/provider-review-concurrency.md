---
name: Provider review concurrency
description: Active-review uniqueness, retry safety, and publication changes must share one concurrency boundary.
---

Member review submission must use an atomic database upsert keyed by provider and member, with uniqueness applying to active reviews only.

**Why:** A read-then-insert permits simultaneous first submissions to race. Soft deletion must retain history without preventing a later review, and a retry must not overwrite intervening administrator moderation.

**How to apply:** Keep partial active-review uniqueness and conflict-aware writes. Treat an identical no-version submission as a retry, not an edit; require a current version for changes and serialize member/admin decisions. Bind existing edits to the original record identity, never composite-key upsert fallback, so deletion or replacement cannot turn a stale edit into creation or mutate a new review. Copy the prior lifecycle state before ORM refreshes when recording history. Edits return to Pending, while Hidden reviews are not member-editable.

Hidden review comments remain private but retain their approved ratings.

**Why:** The established hide-comment policy conceals text rather than removing an approved rating; pending and rejected submissions must not change provider ratings.

**How to apply:** Preserve this distinction in every aggregate and privacy projection. Backfill legacy visibility without inventing historical human approval or moderation events.