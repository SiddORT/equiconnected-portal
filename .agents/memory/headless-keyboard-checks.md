---
name: Headless keyboard checks
description: Reliable activation checks in disposable CDP-driven browser sessions.
---

For CDP keyboard checks, bring the page to the foreground, enable focus emulation,
and include the Enter text payload when sending Enter key-down. Assert the
resulting UI change, not merely `document.activeElement`.

**Why:** A disposable headless session could report the expected focused button
while Enter did not activate it. Foreground/focus emulation and a complete Enter
event made the same shipped controls activate correctly. A mouse-only follow-up
would have hidden the missing keyboard evidence.

**How to apply:** Use this setup for synthetic portal/browser checks. Check the
selected tab or retry result after dispatch, and keep API interception enabled
before navigation.
