---
name: Npm integrity recovery
description: Safe diagnosis and repair of persistent npm EINTEGRITY failures behind the Replit package firewall.
---

When repeated cache-cleared installs return the same checksum mismatch, compare the lockfile integrity with the package registry’s published `dist.integrity`. Correct the lock only when the downloaded checksum matches that authoritative metadata.

**Why:** Retries cannot repair a deterministically incorrect lockfile checksum, while disabling integrity checks would hide real tampering or corruption.

**How to apply:** Keep a small cache-refresh retry for transient failures. If the mismatch remains identical, query the exact package version’s published integrity, preserve the locked version, update only the incorrect checksum, and validate through the actual post-merge setup.