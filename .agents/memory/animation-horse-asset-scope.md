---
name: Animation horse asset scope
description: Records the durable local and replaceable horse-asset boundary for the cinematic animation.
---

# Animation horse asset scope

The accepted baseline is a locally served open-source animated adult horse GLB with a procedural pony fallback; higher-fidelity assets remain replaceable through the same boundary.

**Why:** The user approved this asset baseline, and local serving avoids a third-party runtime dependency while preserving a clear upgrade path.

**How to apply:** Keep the scene timeline independent from model loading and handle any higher-fidelity horse/pony replacement as separate follow-up work.