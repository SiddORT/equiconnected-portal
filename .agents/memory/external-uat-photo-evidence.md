---
name: External UAT photo evidence
description: Evidence and authorization boundaries for UAT provider-photo routing repairs.
---

For UAT photo repair, distinguish local tests, direct API origin delivery,
origin reverse-proxy delivery, public CDN delivery, and on-disk file evidence.
Never report local static-serving or retry UI improvements as a deployed repair.
A public missing-image response returning HTML/200 demonstrates incorrect
routing but does not establish whether historical image bytes exist.

**Why:** The user renewed this repair because earlier UI retry work and operator
instructions had not corrected the actual UAT routing failure.

**How to apply:** Inspect the actual upstream and active proxy rules before
claiming a server-specific correction. If unavailable, report that blocker.
External server/CDN mutations require explicit authorization beyond task approval;
synthetic account sign-in/uploads/profile saves require separate authorization.
Use a designated non-private existing synthetic image for origin/public decoding
and hash comparisons; do not modify provider records to demonstrate success.
