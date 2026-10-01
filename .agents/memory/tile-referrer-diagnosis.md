---
name: Tile referrer diagnosis
description: Distinguish tile-policy compliance from proof of an external service block.
---

Treat a missing tile Referer as a policy mismatch, not conclusive proof of an
OpenStreetMap block.

**Why:** Real Replit-served browser requests without Referer still returned
geographic tiles during investigation of a reported blocked dashboard. Service
enforcement can differ by client origin, network and cache state.

**How to apply:** Preserve global URL privacy; use a tile-only origin policy.
Inspect real browser headers and rendered images, preserve ordinary caching,
and report whether the original external failure was actually reproduced.