---
name: Provider feedback privacy boundary
description: Own-listing feedback may include hidden content, but never structured reviewer identity or private moderation notes.
---

Providers may read all non-deleted reviews on their own listing, including rating-only, pending, rejected, and admin-hidden content. This permission must never widen member/public review visibility or grant providers mutation rights.

**Why:** Providers need moderation transparency without gaining review-management permissions or access to member identity and private moderation conversations.

**How to apply:** Keep provider feedback projections separate from administrator serializers. Mask structured names before sending provider responses, including legacy Account feedback. Use conservative initials only; do not infer labels from emails or unstructured legacy display names. Keep member-directed and internal notes, administrator identity, and reviewer identifiers out of provider review payloads. A published lifecycle state with a legacy hidden-comment flag must still be labelled Hidden by admin for its provider.
