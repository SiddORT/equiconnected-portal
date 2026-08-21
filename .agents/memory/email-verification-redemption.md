---
name: Email verification redemption
description: Security and frontend lifecycle rules for public account email verification.
---

Email-verification tokens must be redeemed under a database row lock (or an equivalent atomic conditional update), and the verification page must issue its redemption request only once per page lifecycle.

**Why:** A read-then-write redemption can allow two concurrent requests to activate the same token, while React Strict Mode can replay an effect and turn a successful single-use redemption into a misleading “already used” failure.

**How to apply:** Preserve transactional consumption whenever verification-token behavior changes. Any frontend route that submits a non-idempotent email token from an effect must use a request guard before calling the API.