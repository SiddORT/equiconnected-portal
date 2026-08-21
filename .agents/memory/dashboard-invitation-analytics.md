---
name: Dashboard activity analytics
description: Reporting definitions for provider, invitation, and public visitor dashboard metrics.
---

The dashboard reports active providers separately from total providers. Invitation analytics use all historical invitations: “Accepted” combines accepted and completed invitations; “Rejected” combines cancelled and expired invitations because the workflow has no distinct recipient-rejected state.

**Why:** The product needs sent, accepted, and rejected invitation reporting without introducing a new invitation-state transition or misrepresenting completed onboarding as unaccepted.

**How to apply:** Preserve these definitions in dashboard and future reporting surfaces. If a true recipient-rejection workflow is added later, report it separately rather than silently changing the existing rejected metric.

Public visitor visits are daily aggregate counts for the landing page, displayed as a rolling seven-day chart. The client records at most one visit per browser per UTC day; the server retains only the date and count, not visitor identifiers, IP addresses, or event-level history.

**Why:** The dashboard needs a useful traffic signal without collecting personally identifiable visitor analytics.

**How to apply:** Keep visitor reporting aggregate-only. Any richer analytics or visitor-level attribution needs an explicit privacy and consent design rather than extending this counter.