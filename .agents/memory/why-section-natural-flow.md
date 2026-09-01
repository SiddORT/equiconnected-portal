---
name: Why section natural flow
description: Product decision and rationale for keeping the public Why EquiConnected section free of scroll pinning.
---

Keep the public Why EquiConnected section in normal document flow without GSAP pinning or scroll-driven card activation. All card titles, descriptions, and actions should remain continuously visible; click and keyboard focus may still provide lightweight CSS state changes.

**Why:** The pinned version repeatedly produced duplicate-looking card layers and missing or faded text across real browsing environments. The user chose reliability and readability over the cinematic scroll treatment.

**How to apply:** Do not reintroduce ScrollTrigger, pin spacers, or fixed-stage transforms in this section. Other homepage sections may keep their existing GSAP behavior.