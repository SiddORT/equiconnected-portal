---
name: Browser interception classification
description: Distinguishing Vite module fetches from application data requests in synthetic browser checks.
---

Do not treat every CDP `Fetch` resource as an application data request: Vite's JavaScript module loading also uses that resource type. Classify API endpoints first, independent of origin and resource type; restrict static exceptions to known local module/asset paths.

**Why:** A fail-closed interceptor that classifies only by resource type can block the entire frontend or report dozens of false fixture errors even when routed messaging checks render successfully.

**How to apply:** When extending synthetic browser interception, prove an unknown absolute API URL is blocked and that local modules still load. Never allow an API request through merely because its resource type or extension looks static.

Match the application API root prefix, not an arbitrary `/api/` substring.

**Why:** Source modules can live under `/src/api/`; treating those module URLs as backend endpoints prevents authentication code from loading even when the synthetic auth response is correct.

**How to apply:** Parse the URL path and classify the backend root before applying the known-local-static allow-list. Keep unknown backend and external requests fail-closed.

Disposable Vite checks must use an optimizer cache separate from the live preview.

**Why:** Starting the live preview alongside a test server with a different config can trigger dependency re-optimization in their shared cache and leave an otherwise valid test waiting for modules.

**How to apply:** Give browser validation configs their own cache directory and allow bounded time for cold optimization in CI.

Prefer a stable Chromium build for long layout matrices, while keeping an explicit executable override.

**Why:** The Replit rolling Chromium 152 browser crashed repeatedly near the end of the messaging matrix, while the installed stable Playwright screenshot browser completed the same matrix. A browser crash is not evidence of a CSS regression.

**How to apply:** Keep browser startup diagnostics and failure reports, use the stable packaged browser where available, and disable GPU acceleration for DOM/CSS-only checks in headless containers (GPU subprocess exits were also observed). Distinguish browser disconnects from layout assertions. Do not silently retry failed layout assertions.