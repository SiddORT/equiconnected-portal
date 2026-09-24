---
name: Frontend test concurrency
description: Interpreting frontend suite timeouts under high test-worker parallelism
---

The frontend test suite can hit widespread five-second timeouts when run at its default worker parallelism in this workspace, even while affected tests pass independently. A full run with two workers passed.

**Why:** Concurrent jsdom workers competed for resources; failures appeared across unrelated pages and a directory thumbnail test failed intermittently. Do not assume a timeout in a broad run implicates the most recent code change.

**How to apply:** When the full suite times out across unrelated tests, reproduce a failing test alone, then run the full suite with constrained worker parallelism before attributing a regression to the change. Keep this distinct from genuinely failing assertions.