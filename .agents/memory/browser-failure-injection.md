---
name: Browser failure injection
description: Keep deliberate API failures visible despite React Strict Mode effect replay.
---

For browser recovery checks, keep the targeted request failing until the error
state is observed and the test explicitly allows the retry. Do not fail only
the first request.

**Why:** Development Strict Mode can replay the loading effect. A single injected
failure may belong to the discarded request while the replacement succeeds,
so the expected error state never appears even though error handling works.

**How to apply:** Scope interception to the endpoint under test, release it
immediately before the user retry action, and require all subsequent real
responses to succeed. Keep authentication and access-boundary assertions
separate from session-fixtured browser presentation checks.