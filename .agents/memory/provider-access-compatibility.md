---
name: Provider access approval compatibility
description: Approval gates for new invited credentials must preserve already activated legacy provider access.
---

Apply the approval requirement to newly submitted invited credentials, not as a retrospective restriction on legacy accounts. Listing publication, operational status, administrator account disablement, and portal approval are separate decisions.

**Why:** The provider-access requirements explicitly exclude re-approving or restricting already activated legacy providers. Treating every under-review listing as an unapproved login would remove existing access; treating every ACTIVE listing as permission to enable an account would undo an administrator's disablement.

**How to apply:** Extend access through explicit ownership only. New credential-bearing invitees wait for explicit approval; legacy first-password paths remain supported. Password recovery must preserve account-enabled, approval, role, and ownership state, and notification failure must not reverse a committed submission or approval.