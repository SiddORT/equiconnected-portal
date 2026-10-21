---
name: Email verification redemption
description: Security and frontend lifecycle rules for public account email verification.
---

Email-verification tokens must be redeemed under a database row lock (or an equivalent atomic conditional update), and the verification page must issue its redemption request only once per page lifecycle.

**Why:** A read-then-write redemption can allow two concurrent requests to activate the same token, while React Strict Mode can replay an effect and turn a successful single-use redemption into a misleading “already used” failure.

**How to apply:** Preserve transactional consumption whenever verification-token behavior changes. Any frontend route that submits a non-idempotent email token from an effect must use a request guard before calling the API. If the route adds a delayed redirect, keep timer cleanup in a mounted-lifecycle guard rather than a per-effect “active” flag: Strict Mode's first cleanup can otherwise suppress the only token response and leave the page indefinitely loading.

Public provider signup verification should end in an awaiting-approval confirmation, not a login invitation or a new authenticated review-status portal. The existing approval email is the sign-in handoff.

**Why:** The user narrowed the verification experience to clear confirmation before approval and explicitly excluded a status portal and additional notification paths.

**How to apply:** Keep member verification navigation separate. Do not broaden provider verification work into new status pages, notification workflows, publication decisions, or retrospective restrictions on legacy provider access.