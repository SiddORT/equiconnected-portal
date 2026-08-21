---
name: Provider photo upload policy
description: Accepted image formats and size limit for provider photo uploads.
---

Provider photo uploads accept JPEG, PNG, GIF, and WebP files up to 10 MB per photo. Enforce the rule in both the browser and the API, and present it next to the uploader.

**Why:** File-selector hints alone can be bypassed or may advertise rules the API does not enforce. Matching validation ensures users receive an accurate limit before they invest time filling photo metadata.

**How to apply:** Keep any future provider-photo uploader or API entry point aligned with this policy. Explain that upload happens only after explicit confirmation, recommend alt text for accessibility, and keep captions optional.