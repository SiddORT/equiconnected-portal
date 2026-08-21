---
name: Provider photo upload policy
description: Accepted image formats and size limit for provider photo uploads.
---

Provider photo uploads accept JPEG, PNG, GIF, and WebP files up to 10 MB per photo. Enforce the rule in both the browser and the API, decode-check streamed image content server-side, and present the rule next to the uploader.

**Why:** File-selector hints alone can be bypassed or may advertise rules the API does not enforce. Matching validation ensures users receive an accurate limit before they invest time filling photo metadata. Provider-owned profiles must also never accept arbitrary image references: that could expose another provider's assets or bypass the owner upload path.

**How to apply:** Keep any future provider-photo uploader or API entry point aligned with this policy. Portal profile saves may retain existing listing photos or use only server-issued uploads under that provider's own path. For published listings, retain uploaded-photo changes inside the pending administrator review request; do not directly attach them to the live listing. Explain that upload happens only after explicit confirmation, recommend alt text for accessibility, and keep captions optional.