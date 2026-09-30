---
name: Home v2 source boundary
description: How to use the supplied Home v2 prototype safely in the public landing page.
---

Use the supplied Home v2 prototype as a visual and content-structure reference, not as an application or data source. Preserve the live member-gated routes, public provider discovery, and subscriber enrollment while adapting its sections. Never copy prototype search controls, named providers, testimonials, ratings, visiting dates, or emergency contacts as if they were live.

**Why:** The reference contains nonfunctional interactions and illustrative entities, while the portal has real authentication and provider data. A visually faithful page can otherwise promise capabilities or availability that the app does not have.

**How to apply:** For future public homepage changes, match the reference's layout and media treatment, but route actions through actual app flows and keep reviews, visiting availability, and emergency guidance truthful until backed by verified data.

Keep actual review comments on member-only provider profiles; the public homepage's review slider should use informational guidance rather than reviewer quotes.

**Why:** The user explicitly chose informational slides for guests instead of making moderated review excerpts publicly visible.

**How to apply:** Do not surface reviewer text on the guest homepage or create a public review-excerpt endpoint without a new explicit decision about broader visibility.

Compare supplied design screenshots at their likely CSS viewport size, not the smaller size shown in chat. High-density captures can look like a narrow desktop screenshot after being scaled down.

**Why:** Comparing a scaled high-density reference to the app at the thumbnail's pixel width makes correctly sized cards appear too large and encourages incorrect layout changes.

**How to apply:** Inspect a reference image's intrinsic dimensions and estimate its capture scale before changing desktop container widths or card proportions.

Treat the prototype's contact phone number, mailbox, and opening hours as examples, not published business details. Contact enquiries should go to the configured admin inbox without exposing that address in the public page.

**Why:** Publishing unverified contact details can send real enquiries to the wrong destination or promise unavailable support hours.

**How to apply:** Keep the visual contact layout, but only show business contact information after it has been confirmed by the owner; keep form-delivery failures visible to visitors.