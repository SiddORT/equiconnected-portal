---
name: Single-panel scroll stories
description: Reliable active-step selection when multiple story steps share one visible sticky content viewport.
---

When story steps share one visible sticky viewport, derive the active step from progress through the outer scroll track rather than observing the overlaid panels. Include any mobile rail that occupies normal-flow space in both active-step and click-target geometry.

**Why:** Overlaid panels occupy the same geometry, so visibility observation cannot distinguish stages. Ignoring a mobile rail’s flow height misaligns transitions, while recomputing immediately during smooth click navigation can visibly revert the requested step.

**How to apply:** Give the outer shell one scroll segment per step, but keep that shell visually transparent so it acts only as scroll runway. Put borders, backgrounds, and shadows on one bounded sticky viewport; otherwise the runway looks like a broken, over-tall panel. On desktop, make the step rail share the viewport height so both columns form one intentional stage; on mobile, reset the rail to content height. Map traveled distance to an index and hold explicit click selection until its segment is reached or the user interrupts. Reset desktop minimum sizes in mobile overrides so sticky controls cannot cover content. Keep the shared stage height content-safe, and size the mobile outer track for the rail plus all overlaid stages so narrow layouts neither overflow nor create trailing scroll space.