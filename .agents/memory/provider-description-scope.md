---
name: Provider description scope
description: Why doctor portal and admin forms omit general Description without deleting historical content.
---

The general Description field belongs to clinic and hospital provider portal profiles and admin add/edit forms. Doctors retain professional biography fields instead of a general Description control.

**Why:** The user requested type-specific editing, not deletion of historical doctor descriptions. Hiding a field must not silently clear its stored value during a later save.

**How to apply:** Omit general description from doctor create/update form payloads; preserve existing text. Clinic and hospital forms should prefill, save, and explicitly clear descriptions normally. Do not broaden this UI change into a database cleanup.