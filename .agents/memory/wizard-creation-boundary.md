---
name: Wizard creation boundary
description: Browser interaction boundary between a wizard's final navigation step and persistence
---

In a wizard, entering a review step must not make the same click or Enter action capable of submitting the form. Native click default behavior can run after a UI update changes the button under the pointer, and a second physical click can land on a newly rendered action. Keep review navigation separate from creation, reject implicit form submissions, and make the creation action unavailable briefly during the transition.

**Why:** A valid Contact & location Continue appeared to show Review & create and then immediately persisted the provider in a real browser. DOM-based tests did not reproduce the native click timing.

**How to apply:** When a wizard changes a footer control from navigation to a destructive or persistent action, use distinct non-submit controls and a deliberate activation boundary; test both implicit keyboard submissions and rapid repeat interactions.