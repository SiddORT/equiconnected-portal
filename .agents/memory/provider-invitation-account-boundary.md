---
name: Provider invitation account boundary
description: Product decision for invitations addressed to an email already used by an EquiConnected account.
---

Provider invitations must not automatically attach to an existing EquiConnected account. Reject the address with a clear duplicate-account message before creating a new invitation, and retain the same restriction for older completed invitations.

**Why:** An existing account may belong to an unrelated person or role. Automatically attaching it would grant provider-portal access without an explicit, auditable authorization decision.

**How to apply:** Keep the account-conflict check in the invitation workflow and explain that a different recipient email is required. Do not add a bypass that links an existing user unless the product owner explicitly chooses a separately designed approval and account-linking flow.