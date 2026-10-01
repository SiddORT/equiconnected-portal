---
name: Contact cutover boundary
description: Why contact encryption requires an offline coordinated cutover rather than mixed plaintext/ciphertext runtime support.
---

Contact-data encryption uses a coordinated maintenance-window cutover with strict encrypted-only runtime reads and database plaintext-write guards. Do not add a permissive legacy plaintext read/write fallback to make an incomplete deployment appear healthy.

**Why:** A mixed-version rollout could leave old processes writing readable contacts after verification, defeating encryption guarantees; a silent read fallback would also conceal missing conversion and corrupted storage.

**How to apply:** Provision the dedicated contact keys through protected tooling, stop legacy writers, preview and convert with the operator tools, authenticate all inventoried records, and complete guarded cutover before resuming traffic. Keep private-messaging keys independent. Production mutation and deployment still require explicit approval.