---
name: Headless Chromium mobile checks
description: Viewport and timing pitfalls when checking the live frontend with a shell-launched browser.
---

For responsive checks narrower than 500px, do not assume Chromium's `--window-size` determines the actual CSS viewport; inspect `innerWidth` and use device metrics emulation when needed.

**Why:** A requested 390px shell-launched headless viewport reported 500px in the page. A direct hash-anchor screenshot also captured a blank transitional frame even though the text was present in the DOM and the page rendered at the root URL.

**How to apply:** Prefer the app preview for visual inspection. For scripted mobile checks, set explicit device metrics and wait until the page has rendered before measuring or capturing; confirm the effective viewport width.

A mobile browser can expand its layout viewport to fit an unbroken text run even when device emulation and the viewport meta tag are correct.

**Why:** A long comma-separated CSV header made the page shrink visually; only the fixed navigation appeared oversized in bounding-box probes, obscuring the actual overflowing text.

**How to apply:** Compare root client width, scroll width, and visual viewport width. Find descendants whose scroll width exceeds client width, not only elements whose bounding boxes extend past the screen. Allow long manual/report text to wrap rather than changing account navigation to compensate.

Browser API interception must match the pathname's API prefix, not a broad URL substring.

**Why:** A wildcard matching any `/api/` segment also catches Vite's source-module URLs under `/src/api/`, replacing JavaScript with fixture JSON and preventing the app from rendering.

**How to apply:** Continue non-API requests unchanged and limit fixture fulfillment to pathnames beginning with the actual API prefix. For URL-pattern interception, use the exact app origin followed by `/api/` so source-module requests pass through unchanged. Enable console-error capture as well as uncaught-exception capture, since module-loading and React errors can appear only in the console.

When using Chromium's debugging protocol directly, select a target with type `page`, not the first target returned.

**Why:** The environment's Chromium wrapper can expose an extension background page ahead of the real tab; navigation and rendering checks against that target appear to time out even with a working frontend.

**How to apply:** Filter the target list before connecting. Return booleans or plain values from layout probes rather than DOM nodes, which cannot be serialized by value. Use instant scrolling and remeasure before dispatching pointer coordinates so smooth scrolling does not invalidate the hit target.
