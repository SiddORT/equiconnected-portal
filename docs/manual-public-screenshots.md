# Getting-started screenshot provenance

Run `python scripts/check-manual-browser.py --capture-public` against the running
frontend to regenerate the five local WebP illustrations listed in
`frontend/src/pages/admin/manual/publicScreenshots.ts`.

These are genuine captures of the shipped public homepage, contact form,
subscription form, and their confirmation states. A fresh dedicated headless
Chromium session uses browser request interception before navigation. Anonymous
authentication, public discovery, aggregate visit recording, and the two
demonstration submissions are fulfilled locally. Other application API requests
fail closed; none are continued to the application backend.

All entered identities and text are synthetic and visibly labelled. Email
addresses use the reserved `example.test` domain. No account, enquiry,
subscription, database record, or email is created. The screenshots exclude
browser address bars, credentials, and invitation/setup links.

| Topic | Genuine captured controls / outcome | Local assets |
| --- | --- | --- |
| `public-find-care-start` | Homepage account journeys and directory navigation | `public-find-care-start.webp` |
| `public-contact-equiconnected` | Populated enquiry form and accepted-submission confirmation | `public-contact-equiconnected.webp`, `public-contact-equiconnected-result.webp` |
| `public-subscribe-updates` | Role/email selections, Keep me posted, and confirmation | `public-subscribe-updates.webp`, `public-subscribe-updates-result.webp` |

The manual links these images through `publicScreenshots.ts`. They are bundled
under `frontend/public/manual`, lazy-loaded as fitted previews, and can be
opened at their original size with the reader's keyboard-accessible dialog.