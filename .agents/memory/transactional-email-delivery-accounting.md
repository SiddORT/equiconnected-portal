---
name: Transactional email delivery accounting
description: How to retain trustworthy SMTP handoff history across caller transaction rollbacks.
---

# Transactional email delivery accounting

For transactional mail, persist an outcome-pending delivery attempt before making the SMTP call, then finalize that same record independently as accepted or failed. Do not put the only log write in the same transaction that may be rolled back after a delivery error.

**Why:** SMTP can accept a message even when the surrounding registration or invitation transaction later fails or rolls back. A post-send-only log would silently lose the history of a real handoff.

**How to apply:** New transactional email paths must use the durable attempt lifecycle, expose only allow-listed failure explanations, and leave a pending record if the process cannot establish the final outcome. For retryable public flows, serialize the recipient identity while claiming and handing off mail so concurrent retries cannot send duplicates.