---
name: Legacy doctor availability
description: Interpretation of doctor records created before scheduling existed.
---

Missing doctor availability classification means unknown, not ongoing or visiting. Never infer historical dates or current availability from Visit Stable, the primary address, or an empty trip list.

**Why:** Older records had no calendar contract. Treating absence as ongoing would claim availability without an administrator confirming it.

**How to apply:** Untouched historical records remain unknown in public and detail displays. The administrator Add/Edit wizard intentionally displays Ongoing when classification is missing, and confirming Save changes accepts and persists that displayed classification even without interacting with the control. Opening or cancelling the editor must never write a classification. Preserve saved Visiting selections and visit history; do not apply this admin default to invitation, signup, or provider-portal flows.