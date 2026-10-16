---
name: Address postal policy
description: Product scope for optional postal codes, UAE defaults, and existing address interfaces.
---

Postal codes are optional for UAE and international manual addresses. Keep every existing postal input visible and editable, in the existing field order and layout; do not replace them with new Emirate/City controls.

**Why:** The user explicitly superseded an earlier country-first redesign with a minimal policy change that preserves the current UI.

**How to apply:** Future address work must preserve populated postal codes and historical blank countries. UAE is an initialization default only for genuinely new addresses, never a hydration fallback for saved profiles, invitations, pending updates, or visit snapshots.

A default country alone must not make an untouched optional address or unscheduled visit count as partially filled.

**Why:** Adding a country default can accidentally activate older “any field filled” submission guards, forcing users to supply an address they did not intend to add.

**How to apply:** Distinguish initialization from user input when evaluating optional-address completeness; retain the existing required fields once an address is actually entered.
