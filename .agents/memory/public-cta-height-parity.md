---
name: Public CTA height parity
description: Why the two landing-page call-to-action sections need rendered-height synchronization.
---

Keep the member invitation section the same rendered height as the later healthcare-network CTA across desktop and mobile widths.

**Why:** The later CTA's content often makes it taller than its declared CSS minimum; matching minimum-height values alone produced visibly different banners.

**How to apply:** When changing either CTA's content or responsive layout, preserve actual-height synchronization. Allow the height to update after fonts load and on viewport changes rather than hard-coding one desktop pixel value.