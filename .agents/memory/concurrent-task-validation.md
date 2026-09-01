---
name: Concurrent task validation
description: How to validate safely when another project task merges into shared files during active work.
---

When another task merges changes into files touched by the current work, treat all earlier validation of those files as stale and rerun the affected focused tests, full build, and diff checks from the new current state.

**Why:** A concurrent merge changed a shared public-page test after it had passed locally, leaving invalid declarations and broken test boundaries that were caught only by the completion review.

**How to apply:** Watch for task-merge updates while working on shared frontend files. After a merge, inspect the current diff and recent history, repair any integration damage, and rerun validation immediately before completion.