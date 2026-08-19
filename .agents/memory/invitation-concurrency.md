---
name: New-provider invitation concurrency
description: Concurrency rule for invitation flows that create a provider draft.
---

New-provider invitation creation must serialize on normalized provider type plus recipient email before creating the draft provider.

**Why:** A uniqueness constraint scoped to provider ID cannot stop simultaneous requests from each creating a different draft provider ID for the same logical recipient. A transaction-scoped logical reservation prevents both duplicate providers and duplicate active invitations.

**How to apply:** Any future path that creates a provider from an invitation must acquire the same logical reservation, re-check for an active invitation, and hold the reservation through the provider/invitation commit.