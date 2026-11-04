---
name: Horse Rider membership
description: Rider identity and its shared Horse Owner flow without extra privileges.
---

Horse Rider is a distinct displayed member account type using the same flow and horse-management capabilities as Horse Owner.

**Why:** The user explicitly requested a Horse Rider choice while keeping its flow the same as Horse Owner, and approved retaining the rider account label.

**How to apply:** Keep rider identity separate from shared authorization capabilities. Include riders in member verification, sign-in, recovery, horse profiles, and discovery without granting stable-manager, provider, or admin access. The existing Both choice remains Horse Owner plus Stable Manager; do not silently redefine it when adding rider features.
