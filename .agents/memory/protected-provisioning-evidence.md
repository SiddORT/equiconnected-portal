---
name: Protected provisioning evidence
description: Validate provisioning evidence and preserve UAT encryption continuity during recovery.
---

A confirmation that protected secrets were saved proves only their presence,
not valid JSON, key length, matching active ID, or operational encryption.

**Why:** Repeated protected-form submissions were confirmed as saved while the
messaging keyring continued to fail JSON parsing. Treating confirmation as
successful provisioning would falsely report recovery.

**How to apply:** Run the existing encryption validator after each operator
submission. Report only safe validation categories, never values or arbitrary
exception payloads. Stop repeated unchanged retries and request operator-side
format correction rather than relaxing validation or generating replacement
keys through unprotected configuration.

Preserve existing UAT encryption and blind-index material during recovery unless
the operator explicitly approves a reviewed rotation. A fresh target database
is not permission to replace that material.

**Why:** The operator retains the previous UAT database as a recovery backup and
requires the running application and administrator seed to use the same
configuration. Replacement keys can invalidate encrypted backup data and its
lookup indexes even when the new database starts empty.

**How to apply:** Diagnose safe validator reason codes and process-level
configuration differences first. Do not generate replacement keys or bypass
actual reuse checks merely to make bootstrap succeed.