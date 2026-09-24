---
name: Legacy doctor availability
description: Interpretation of doctor records created before scheduling existed.
---

Missing doctor availability classification means unknown, not ongoing or visiting. Never infer historical dates or current availability from Visit Stable, the primary address, or an empty trip list.

**Why:** Older records had no calendar contract. Treating absence as ongoing would claim availability without an administrator confirming it.

**How to apply:** Preserve unknown classification on legacy edits until an admin explicitly chooses one; distinguish an unscheduled visiting doctor from an ongoing doctor in admin displays.