---
name: GSAP context cleanup registration
description: How to defer event-listener and other manual cleanup when using gsap.context.
---

`context.add(callback)` executes `callback` when it is registered. Passing a callback that directly removes listeners therefore removes them during setup instead of teardown.

**Why:** GSAP 3.15 invokes the registered callback immediately, so treating it as a teardown callback can silently disable interactions during setup.

**How to apply:** Remove manual listeners in the owning effect cleanup before `context.revert()`, or register a context callback that returns the actual cleanup function.