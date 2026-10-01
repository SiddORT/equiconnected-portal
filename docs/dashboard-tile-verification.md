# Dashboard tile referrer verification

Verified on October 1, 2026 with Chromium on the HTTPS Replit development
page `/admin/dashboard?invitation_token=privacy-check&tab=map`.
Admin authentication and dashboard data were browser-only fixtures; the app's
actual DashboardMap and Leaflet ran unchanged, and OSM requests were not mocked.
No credentials or persisted provider data were used.

## Diagnosis

The original tile requests had no `Referer` header. The document declares
`no-referrer`, and Leaflet's default tile policy does not override it.
[OSMF's current tile policy](https://operations.osmfoundation.org/policies/tiles/)
requires website requests to include a valid Referer and prohibits a policy
that suppresses it.

However, the baseline session returned HTTP 200 geographic images for all
12 initial tile requests. The reported 403 was not reproduced in this
environment. The missing header is a confirmed policy mismatch and a plausible
cause, not proof of the original block. No current external restriction was
observed; another origin, network, or cached block could still be affected.

## Fixed behavior

- Leaflet tile images explicitly use `strict-origin`.
- HTTPS tile requests identify only the Replit application origin, ending in
  `/`. The admin path and the test invitation token/query never appear in
  the header.
- The document remains `no-referrer`; the tile endpoint, zoom limit and visible
  attribution are unchanged.
- Real tile responses were HTTP 200 and loaded 256-pixel geographic images.
  Browser disk caching remained enabled, with cache hits during repeated
  filter views. No cache-bypass headers, proxy, alternative provider or
  retries were introduced.
- Hospital, Clinic and Doctor toggles removed/restored the corresponding
  markers; popups retained provider/address information. Zoom increased the
  tile zoom level, attribution remained visible, and both the all-hidden and
  no-coordinate empty states passed.
- A normal cache-aware reload verified the no-coordinate state.
- No browser exceptions were observed.

## Reproduce

Start the existing Frontend workflow. Start Chromium with remote debugging on
port 9222 and use `python scripts/check-dashboard-tiles-browser.py fixed`.
The script requires the existing Python `websockets` package and
`REPLIT_DEV_DOMAIN`. It writes request evidence and a screenshot under
`screenshots/dashboard-tiles-fixed.*`; it does not alter the database.

Affected map and dashboard tests passed (9 tests), as did
`cd frontend && npm run build`. Existing Vite configuration and bundle-size
warnings remain unrelated to this fix.