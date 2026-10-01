---
name: Invitation contact email suggestion
description: How to treat the invitation delivery address in provider profile contact fields.
---

Treat the invitation recipient as a suggested provider contact email, not a mandatory or immutable listing address. The invitee can remove it or add other contact emails, and saving an empty list is an intentional choice that must persist across visits.

**Why:** Invitation delivery identifies who received access to edit a profile; it does not prove that address should remain publicly listed. Existing-provider invitations may already have other contact addresses, so prefill must not overwrite them before the invitee saves.

**How to apply:** Keep invitation account identity separate from profile contact details. Suggest the recipient until the invitee explicitly saves the email collection, including an empty collection; never silently reinsert the suggestion afterward.

Portal contact edits and invitation contact edits have different legacy-scalar semantics. Portal saves mirror the chosen primary collection contact (or null for an empty list) so signup scalar fallbacks cannot resurrect removed contacts. Invitations deliberately remove their recipient scalar once the collection is edited. Do not impose portal scalar mirroring on a writer shared with invitations.

**Why:** Applying portal mirroring to the shared invitation writer changed an established invitation behavior and broke its removal/replacement regression.

**How to apply:** Keep scalar synchronization at the portal save/approval boundary; preserve invitation suggestion semantics and never change account login identity through either profile editor.