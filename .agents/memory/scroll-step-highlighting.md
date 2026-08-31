---
name: Scroll-driven step highlighting
description: Reliable active-step selection for sticky rails driven by multiple scrolling content panels.
---

Keep the latest intersection ratio for every observed panel and derive the active step from the complete retained set. Do not choose only among entries delivered in one observer callback.

**Why:** An IntersectionObserver callback contains elements that crossed configured thresholds, not necessarily every panel currently visible. During overlapping transitions, selecting from callback entries alone can highlight a less-visible panel.

**How to apply:** Use sufficiently granular thresholds, update stored ratios for each delivered entry, and select the greatest ratio across all panels. Cover both scroll directions and overlapping panels in a deterministic test.