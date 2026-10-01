# Synthetic messaging layout gate

From the repository root, install the frontend with `npm ci --prefix frontend`
and Python tooling with
`python3 -m pip install -r scripts/requirements-messages-browser.txt`.
Install Chromium/Chrome and set `CHROMIUM_BIN` to its executable if it is not on
PATH (Replit's packaged stable screenshot browser is also detected, with the
rolling tool browser used only as a last resort).

Run `cd frontend && npm run test:messages-browser`. This starts a disposable
local Vite server without backend proxies or env files and a fresh browser
profile, then stops both on success, failure or interruption. No backend,
Replit preview variables, account credentials or live conversations are needed.
`npm run test:messages-browser:harness` deliberately breaks layout and injects an
unknown absolute API URL to verify failure evidence and process cleanup.
Both commands run in `.github/workflows/messages-layout.yml` on PRs and main pushes.

To target an already-running **development frontend** instead:
`npm run test:messages-browser -- --app-url http://127.0.0.1:5000`
(or set `MESSAGES_APP_URL`). This mode does not stop the supplied frontend.
Do not target production.

All API/data requests, including absolute URLs on other origins, are intercepted
before navigation. Unknown fixtures fail closed. Only frontend static resources
are allowed through; external font stylesheets receive empty synthetic CSS to
avoid a network dependency. The gate therefore measures layout using local
fonts/fallbacks, not availability of remote font services.

Failure screenshots carry a synthetic-data label. `failure.json` records the
case and safe fixture request paths; frontend/Chromium startup logs are also
saved in `screenshots/messages-theme/` (gitignored). CI uploads this directory
on failure and retains it for seven days. Startup failures may have logs rather
than screenshots. Each run clears previous failure screenshots/reports.