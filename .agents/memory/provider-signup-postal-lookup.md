---
name: Provider postal lookup
description: Decision about ambiguous international postal-code matches during signup and admin creation
---

For public provider signup and Admin Add Provider, treat a postal code as a lookup query rather than a unique location key. Present matching places and require an explicit choice before filling country, state, and city. Keep manual correction available when lookup fails or the source is incomplete.

**Why:** The user did not limit signup to a single country; real codes such as 110001 can resolve to several countries. Auto-picking the first result would silently save the wrong registered location and affect stable-visit radius.

**How to apply:** Preserve candidate selection and an explicit no-match/unavailable state when changing either form's lookup provider or location controls. Never infer country from the postal code alone without a verified unique match.