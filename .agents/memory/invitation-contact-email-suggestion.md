---
name: Invitation contact email suggestion
description: How to treat the invitation delivery address in provider profile contact fields.
---

Treat the invitation recipient as a suggested provider contact email, not a mandatory or immutable listing address. The invitee can remove it or add other contact emails, and saving an empty list is an intentional choice that must persist across visits.

**Why:** Invitation delivery identifies who received access to edit a profile; it does not prove that address should remain publicly listed. Existing-provider invitations may already have other contact addresses, so prefill must not overwrite them before the invitee saves.

**How to apply:** Keep invitation account identity separate from profile contact details. Suggest the recipient until the invitee explicitly saves the email collection, including an empty collection; never silently reinsert the suggestion afterward.