---
name: Protected provisioning evidence
description: Distinguish secret-form confirmation from successful encryption activation.
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