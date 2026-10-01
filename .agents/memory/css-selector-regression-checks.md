---
name: CSS selector regression checks
description: Testing nested-control style isolation despite Vitest CSS import stubbing.
---

For selector-isolation regressions, parse the actual stylesheet rather than trusting a CSS import to contain source text; map module class names to the rendered DOM before checking selector matches.

**Why:** In this frontend's Vitest configuration, a CSS module imported with a raw query still resolved as a stub rather than a source string. DOM-only interaction tests also cannot reveal a search input collapsed by an ancestor's descendant selector.

**How to apply:** Read stylesheet text from disk in the test, use CSSOM to inspect relevant selectors, and pair those checks with real-browser dimensions and focus inspection. Include both coarse-pointer and non-touch narrow viewports; JSDOM is not a layout engine.