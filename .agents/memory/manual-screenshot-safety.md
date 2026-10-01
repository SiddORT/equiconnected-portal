---
name: Illustrated manual screenshot safety
description: Privacy and isolation requirements when updating the portal's illustrated manual.
---

Manual illustrations must be genuine captures of the shipped interfaces with explicitly labelled synthetic data. Never use live accounts, real messages, contact records, credentials, or active invitation/setup links to produce documentation.

**Why:** The combined guide covers administrative decisions, access emails, and private member workflows. Capturing those against live data risks exposing private information or causing real approvals and email delivery.

**How to apply:** Use a disposable browser session with fail-closed API interception enabled before navigation. Fulfill every application API request from synthetic fixtures, including authentication and writes; unknown routes must fail rather than reach the backend. Preserve screenshot provenance and refresh captures when shipped controls change. Do not change workflow behavior merely to match documentation.