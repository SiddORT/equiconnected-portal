---
name: Contact enquiry acceptance
description: Why stored enquiries, rather than optional notification delivery, define public contact acceptance.
---

Once an enquiry is committed, public contact acceptance is final even if optional team notification fails, is unconfigured, or its delivery accounting cannot finish. Keep repeated enquiries from the same sender separate.

**Why:** Asking a visitor to resubmit an already-saved enquiry would create duplicates; sender-based deduplication would instead discard legitimate later messages.

**How to apply:** Future changes to contact notification or delivery accounting must not turn a durable acceptance into a retry response. Use validated request values during SMTP, not expired ORM objects that can silently reopen a database transaction after commit.