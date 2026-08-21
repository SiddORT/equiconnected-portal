---
name: Collapsible admin filters
description: Accessibility rule for collapsible admin-list filter controls.
---

When an admin filter panel is collapsed, conditionally render its controls only while it is open rather than relying solely on a zero-height, overflow-hidden container.

**Why:** Visually clipped controls can remain reachable by keyboard navigation and may be exposed to browser automation or assistive technology despite the panel reporting that it is collapsed.

**How to apply:** For new or updated collapsible filter panels, keep the trigger accessible with `aria-expanded`, preserve selected-filter summaries outside the panel, and mount the filter inputs, tabs, and clear action only in the expanded state.