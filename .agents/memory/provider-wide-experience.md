---
name: Provider-wide experience
description: Why years of experience is provider-wide while the legacy doctor profile still carries a compatible copy.
---

Years of experience applies to every provider type. Use the provider-wide value as the canonical value in invitations, admin editing, provider account editing, and detail views. When updating a doctor, keep the older doctor-profile value synchronized; when reading a historical doctor record without a provider-wide value, fall back to the doctor-profile value.

**Why:** Doctor profiles historically stored their own years of experience, while other provider types already had a provider-level field through registration but could not consistently edit or view it. Dropping the doctor copy would break older API consumers and obscure historical values.

**How to apply:** Carry the field through new provider-facing flows regardless of provider type; preserve zero as a valid value and use null-only fallback for old doctor records. Do not apply doctor-only validation to provider-wide experience.