---
name: Contact cutover boundary
description: Why contact encryption requires an offline coordinated cutover rather than mixed plaintext/ciphertext runtime support.
---

Contact-data encryption uses a coordinated maintenance-window cutover with strict encrypted-only runtime reads and database plaintext-write guards. Do not add a permissive legacy plaintext read/write fallback to make an incomplete deployment appear healthy.

**Why:** A mixed-version rollout could leave old processes writing readable contacts after verification, defeating encryption guarantees; a silent read fallback would also conceal missing conversion and corrupted storage.

**How to apply:** Provision the dedicated contact keys through protected tooling, stop legacy writers, preview and convert with the operator tools, authenticate all inventoried records, and complete guarded cutover before resuming traffic. Keep private-messaging keys independent. Production mutation and deployment still require explicit approval.

Pre-conversion backup verification must use raw database snapshots rather than hydrating contact-bearing ORM objects.

**Why:** The application deliberately rejects plaintext contact reads. ORM-based maintenance planning therefore cannot inspect a database that is still awaiting conversion, even when its schema and keys are ready.

**How to apply:** Before cutover, verify a private database archive through an isolated restore and raw row/sequence digests. Do not relax the encrypted-only reader to make backup verification work.