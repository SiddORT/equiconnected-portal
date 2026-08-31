---
name: Homepage carousel selection
description: Interaction rule for horizontally scrollable homepage card rails with an explicit selected state.
---

Treat arrow controls and card activation as explicit selection. Let touch, wheel, and drag scrolling browse the rail without changing that selection unless the active card can be derived reliably across every responsive card count.

**Why:** Inferring selection from `scrollLeft` and one card stride breaks near the end of multi-card rails, where the browser cannot scroll the selected final card to the leading edge. That can overwrite a user’s real choice with a neighboring card and make live accessibility text misleading.

**How to apply:** Label live feedback as “Selected …” when it represents an explicit choice. If a future carousel must follow passive scrolling, derive the card nearest the viewport center and preserve programmatic selections through their scroll events.