---
name: Aggregate retry expiry
description: Why privacy-minimal click receipts need independently bounded event age as well as expiration.
---

An expiring UUID-only receipt is not enough to prevent a delayed retry from
becoming a second count. Keep the event's retry eligibility bounded independently
of whether its receipt still exists; use the activation timestamp encoded in a
UUIDv7 rather than retaining event-linked identity or contact information.

**Why:** The provider contact measurement contract requires both temporary,
unlinkable retry receipts and duplicate-safe delivery. Receipt cleanup alone
would allow a replay to count again after deletion. Timestamped keys preserve
that privacy boundary while making expired events rejectable.

**How to apply:** Keep browser key generation, server age/future-skew validation,
receipt expiration, and system-calendar bucketing consistent. Retry the same key
only within the accepted window. Do not change to untimestamped keys without
another independent age check. Tracking must remain optional for native actions.