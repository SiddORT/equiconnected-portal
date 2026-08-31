---
name: Nested frontend package installs
description: Replit package-helper behavior for projects whose JavaScript application lives below the workspace root.
---

# Nested frontend package installs

When a JavaScript app lives in a nested directory, do not assume the package helper updated that app’s manifest or lockfile just because installation succeeded.

**Why:** The helper can target the workspace root and initialize a new root package instead of the nested application, leaving the real app’s package metadata unchanged.

**How to apply:** After adding packages to a nested app, verify the intended manifest, run a clean-install dry run against its lockfile, and remove any accidental root package metadata before delivery.