# Provider first-password setup investigation

## Findings (2026-10-01)

The reported failure is **not reproduced** with synthetic eligible accounts.
The original failing HTTP status and response body were not available, so no
specific network, routing, validation, or server failure can be assigned as its
cause. No supplied token was redeemed; no real account was reset or changed.

The investigation's prior read-only checks found the supplied token eligible
at the time checked: present, unexpired, unused, not invalidated, with matching
direct-provider ownership, pending account state, and a saved contact email.
That establishes eligibility, not the result of the original request.

The confirmed presentation defect was the setup page's generic fallback:
network errors and unrecognized responses could display “link is invalid.”
Only a missing token or an explicit `provider_portal_link_invalid` response
now receives that classification. Expired and used/replaced links remain
distinct. Connectivity, rate limiting, validation, temporary service failures,
and unexpected responses receive specific or cautious recovery instructions.

The frontend previously did not enforce the API's 128-character password
maximum or verify the success response shape. These are now covered, but
neither was established as the cause of the reported failure.

## Evidence

- `python -m pytest tests/test_direct_provider_access.py tests/test_provider_portal.py -q`
  from `backend`: 30 tests passed. Synthetic direct and invitation accounts
  receive fresh links through mocked email delivery, redeem them via the
  actual HTTP endpoint, sign in, and access their owned provider profile.
- Tests cover invalid, expired, replaced and single-use links, ownership
  restrictions, and password-validation rejection.
- A synthetic audit failure after the in-memory password/activation/token
  changes returns HTTP 503. Database refresh proves the old password hash,
  pending/inactive/unverified account, and unused token survive. Retrying the
  same link after recovery succeeds and permits sign-in.
- Frontend setup-page and API-contract tests: 19 passed. Cases include missing,
  invalid, expired, used/replaced, network, 503, 429, 422, unknown 404, and
  malformed HTTP 200 responses; retry preserves entered fields.
- `npx tsc -b` from `frontend` passed.
- Both managed development workflows started successfully. A browser capture
  of `/provider/setup-password` rendered the missing-token error and disabled
  submit control. The browser's anonymous session-refresh 401 responses are
  separate from password setup; this capture did not submit a setup request.

## Diagnostic limits and safe next steps

SMTP was mocked to capture synthetic setup links, not to send test messages to
real recipients. Backend integration tests use an isolated PostgreSQL test
schema. They do not prove delivery or behavior in the published environment.
The external development-domain HTTP probe failed TLS/connectivity from this
container; it supplied no usable setup HTTP response. The local preview
rendered successfully, but that is not evidence about the original request.

If the issue recurs, record the request timestamp, HTTP status, content type,
and structured error code for **POST**
`/api/v1/auth/provider-portal/setup-password`. Do not export a full HAR, URL
query string, request body, raw token, password, cookies, or authorization
headers. A controlled synthetic account should be used for reproduction.

Unexpected setup exceptions are rolled back and log only the fixed event
`provider_portal.password_setup_unavailable`, without exception parameters.
Network failures cannot establish whether the server committed before the
response was lost, so the page suggests trying sign-in before retrying.
Expiry, ownership, and single-use rules have not been relaxed.