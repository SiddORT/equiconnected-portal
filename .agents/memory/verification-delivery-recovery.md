---
name: Verification delivery recovery
description: Transaction and privacy boundaries for signup verification mail and retries.
---

Persist member and provider registrations before attempting verification mail. Resend must lock the account identity through the SMTP handoff, use independently durable delivery history, and replace prior links only after a successful handoff. Keep the public resend acknowledgement identical and return it before account lookup or network delivery.

**Why:** The former SMTP-before-commit path discarded valid signups on transient mail failures. Synchronous anonymous lookup/delivery can also leak account existence through response time, and parallel retries can issue competing links.

**How to apply:** Preserve this boundary when changing signup, SMTP, or verification recovery. A historical generic delivery failure cannot be attributed to an SMTP stage after the fact; use only safe categories on future attempts.