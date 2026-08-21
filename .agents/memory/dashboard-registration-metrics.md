---
name: Dashboard registration metrics
description: Semantics for public-signup aggregates displayed on the administrator dashboard.
---

Registration dashboard metrics include only users assigned the `horse_owner` or `stable_manager` role. A request is approved only after email verification activates the account; a rejected request is a verified public account that was subsequently deactivated.

**Why:** Invitation records and anonymous website traffic are unrelated to public account registration, and unverified signups are pending rather than rejected.

**How to apply:** Keep role totals distinct by account role, count a dual-role account once in the request total, and do not repurpose website-visit or invitation data for registration reporting.