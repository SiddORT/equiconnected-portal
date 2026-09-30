---
name: Invitation service compatibility
description: Why token-based provider invitation service validation is opt-in for newer clients.
---

The invitation form sends explicit service details and must complete a positive stable-visit radius and valid emergency contact number when those options are enabled. Older token API clients that do not send service details must remain able to submit without backfilling the new controls.

**Why:** The invitation endpoint already had clients and historical provider drafts before the service controls were added; globally requiring new fields would reject otherwise valid older submissions.

**How to apply:** Enforce conditional service completeness on submissions that participate in the service-details contract, while clearing dependent values when options are turned off. Do not remove the legacy submission path as part of an unrelated form change.