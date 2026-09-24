---
name: Admin provider form compatibility
description: Versioned validation boundary for the revised admin add-provider experience
---

New Admin Add Provider submissions explicitly opt in to stricter form rules. Existing API callers without that opt-in must continue to create or edit their older, less-complete provider records. Apply the stricter required email, location, and conditional service rules on new form submissions without making previously valid API payloads invalid.

**Why:** The provider API predates the revised form and permits partial records. Enforcing new required fields globally broke many existing create flows and tests; legacy records also lack some fields, so unrelated edits cannot require a complete historical backfill.

**How to apply:** When expanding provider validation, preserve a compatible path for old clients and legacy edits. Keep cross-field validation on fields actively changed by the revised form, and avoid silently clearing legacy values during unrelated updates.

The guided step-by-step experience applies to both admin provider creation and editing, not public invitation drafts.

**Why:** Administrators need consistent controls and an explicit review before either persistence action. Edits can involve incomplete legacy records, so their wizard gates cannot inherit creation-only required fields. Invitation drafts have a separate save/submit workflow.

**How to apply:** Apply wizard navigation to both admin modes, with mode-specific validation, and leave invitation drafts outside the wizard.