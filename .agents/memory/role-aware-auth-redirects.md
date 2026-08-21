---
name: Role-aware auth redirects
description: Prevent redirect loops between authentication pages and role-protected routes.
---

Admin authorization guards and the admin sign-in screen must choose destinations based on the authenticated user’s role. Members who attempt an admin route should go to their member destination, while only administrators may be auto-forwarded from the admin sign-in page to an admin route.

**Why:** Sending a member from an admin-only guard to the admin sign-in page while that page forwards every authenticated user back to the dashboard creates an immediate two-route navigation cycle. Browsers surface this as an update-depth error and leave the app appearing blank or permanently loading.

**How to apply:** Whenever adding a protected route or auto-redirect, trace both the denied-route redirect and the sign-in-page authenticated redirect for every supported role. Keep an automated test for a signed-in member visiting both the protected admin route and the admin sign-in URL.