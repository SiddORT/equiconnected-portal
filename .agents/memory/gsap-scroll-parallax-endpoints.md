---
name: GSAP scroll parallax endpoints
description: Reliable setup for subtle, scrubbed decorative parallax on the public site.
---

Use explicit `fromTo` transform endpoints for scrubbed ScrollTrigger parallax rather than a single destination-only tween.

**Why:** A destination-only parallax tween appeared transformed but remained at the same end-state offset throughout the tested scroll range, making the effect visually static.

**How to apply:** For decorative scroll-linked movement, define restrained positive and negative transform endpoints, use a scrubbed trigger spanning the element’s viewport passage, and verify transforms at multiple scroll positions. Disable the entire setup for reduced motion.