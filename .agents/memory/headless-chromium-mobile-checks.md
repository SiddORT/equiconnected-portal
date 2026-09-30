---
name: Headless Chromium mobile checks
description: Viewport and timing pitfalls when checking the live frontend with a shell-launched browser.
---

For responsive checks narrower than 500px, do not assume Chromium's `--window-size` determines the actual CSS viewport; inspect `innerWidth` and use device metrics emulation when needed.

**Why:** A requested 390px shell-launched headless viewport reported 500px in the page. A direct hash-anchor screenshot also captured a blank transitional frame even though the text was present in the DOM and the page rendered at the root URL.

**How to apply:** Prefer the app preview for visual inspection. For scripted mobile checks, set explicit device metrics and wait until the page has rendered before measuring or capturing; confirm the effective viewport width.