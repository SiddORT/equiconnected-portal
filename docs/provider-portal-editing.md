# Provider portal editing: field inventory and UAT photo routing

## Field ownership inventory

| Field group | Administrator editor | Provider portal |
| --- | --- | --- |
| Practice/display name, website | Yes | Basic details |
| Description (clinic/hospital) | Yes | Basic details; historical doctor description is preserved, not rewritten |
| Doctor first/last names | Yes | Added to Basic details; both empty preserves a legacy name-only listing; both populated use `First Last` as the listing name |
| Languages (all types) | Yes | Added to Basic details; catalog choices with retained inactive selections labelled |
| Years of experience (all types) | Yes | Professional details, including zero |
| Doctor title, biography, experience notes, qualifications | Yes | Professional details |
| Specializations | Yes | Services |
| Stable/home visits, radius, emergency services/number | Yes | Services; independent of doctor classification |
| Doctor Ongoing/Visiting | Yes | Added to Services; unspecified legacy values remain unspecified on unrelated saves |
| Recorded doctor visits | Add/read | Read-only Previous/Current/Upcoming; no editing/deletion |
| Additional doctor visits | Add | Existing Visits interface; immediately available for draft Visiting selection |
| Addresses, coordinates, optional postal codes, primary location | Yes | Contact & location; fresh addresses default to UAE, saved addresses retain their values |
| Contact phone/email collections and primary selection | Yes | Contact & location; these are listing contacts, not login credentials |
| Photos, title, alt text, order, cover selection | Yes | Explicit local selection → upload → profile save; current approved photos stay separate from pending/rejected proposals |
| Provider type, operational status, publication | Yes | Deliberately admin-only |
| Verification, approval/rejection decisions, internal audit/moderation | Yes | Provider sees only own review state/rejection feedback, never private moderation data |
| Account activation, login identity/password, ownership/linking, invitations/setup | Admin/access workflows | Deliberately excluded from this editor |

No additional provider-owned input was found in the current shared administrator
profile form beyond the three added groups. Database attributes that are not
offered as profile inputs there (for example legacy emergency-contact name and
clinic/hospital-visit metadata) are not copied into this task's editor.

Published changes remain proposals. Approval locks the provider and request,
revalidates the schedule, then applies classification and additions in one
transaction. Same-day visits are allowed; overlapping inclusive endpoints are
not. Approval delays do not retrospectively invalidate unchanged submitted
dates. Recorded trip IDs/location snapshots are never replaced by profile edits.
Proposed additions must be explicitly removed before an incompatible selection.

## UAT diagnosis — read-only evidence, 2026-10-21

The supplied screenshot shows an uploaded, not-yet-saved photo with a broken
stored-image preview. Its exact UUID/filename is not visible. No account was
signed into, no record modified, no notification sent, and nothing deployed.

A read-only GET to this deliberately nonexistent path:

```
https://uat.equiconnected.com/uploads/providers/00000000-0000-0000-0000-000000000000/photos/portal-routing-probe.png
```

returned **HTTP 200**, **Content-Type: text/html**, through Cloudflare.
The body starts `<!doctype html><html lang="en">` and contains the SPA entry
page, not an image. A nonexistent image must instead return 404; a known file
must return its image content type and decodable bytes. This proves the UAT
`/uploads/` path falls through to HTML for at least missing assets. It does not
prove whether the screenshot's original file exists, or whether an origin file
permissions/storage issue also exists. Origin configuration and storage were
not accessible from this workspace. **UAT is not claimed fixed.**

Application paths are consistent: both upload storage and FastAPI's static mount
use `backend/uploads`; Vite proxies `/uploads` to FastAPI on port 8000. Tests
upload real JPEG/PNG/GIF/WebP bytes and decode the FastAPI-served URL. Browser
fixture checks are synthetic UI evidence, not UAT origin/storage evidence.

## Required external configuration (server operator; not executed here)

Add the following location to the existing UAT Nginx TLS server block, before
the SPA fallback. Use the **same upstream as the existing `/api/` route**;
8000 below is this project's documented FastAPI port, not an independently
verified UAT process port:

```nginx
location ^~ /uploads/ {
    # No trailing slash: preserve /uploads/... for FastAPI's static mount.
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_intercept_errors off;
}
```

Do not rewrite image 404s to `/index.html`, strip `/uploads`, or use the
frontend build folder as the uploads directory. Disable any Cloudflare rule
that rewrites/caches missing `/uploads/*` as HTML; purge affected cached HTML
responses after changing the origin. Keep the existing SPA fallback only for
frontend routes. Preserve the existing upload body-size limit (multipart
overhead requires a proxy limit above the 10 MB **per-image** application cap).

The application service user needs read/write access to the persistent
`/var/www/nodejs/uat.equiconnected.com/backend/uploads` directory. Keep that
directory across releases/restarts and on shared storage if multiple workers
run on different hosts. Do not move storage or delete existing files as part
of this routing repair. The deployment script does not configure Nginx or
establish persistent storage; it merely checks and reloads existing Nginx.

### Verification after the operator applies the configuration

1. Validate with `nginx -t`; reload only after it passes.
2. On the origin, request a known existing, non-private synthetic image from
   `http://127.0.0.1:8000/uploads/...` (substitute the actual API port) and
   confirm 200, `image/png` (or the corresponding supported type), and real
   decodable bytes. Compare the filename to the file under `backend/uploads`.
3. Request that **same path** through `https://uat.equiconnected.com` and verify
   the same status/content type and byte checksum. A mismatch isolates the
   proxy/CDN; an origin 404 indicates missing files, while 403/500 warrants
   service-user permission and origin-log inspection.
4. Request the nonexistent probe above through origin and UAT. Both must
   return **404**, never HTML/200. Check GET bodies, not only HEAD responses.
5. With a designated synthetic UAT account and separate authorization for test
   writes, check local selection, explicit upload, profile save, reload, admin
   review and approved gallery. Until then do not make live decisions to test
   this change. Existing record checks can remain read-only.

Example read-only public-path checks:

```sh
curl -sS -D /tmp/photo-headers -o /tmp/photo-bytes \
  'https://uat.equiconnected.com/uploads/<known-synthetic-image-path>'
grep -Ei 'HTTP/|content-type:|cf-cache-status:' /tmp/photo-headers
python -c 'from PIL import Image; im=Image.open("/tmp/photo-bytes"); im.load(); print(im.format, im.size)'
```

An inaccessible stored photo now displays a clear error and retry action in
the portal; admin review keeps metadata and offers retry. Temporary local blobs
are never used to disguise failed stored-image requests.

## Local verification

- Backend provider, portal and moderation suites passed in the dedicated pytest
  schema, including real static-URL decoding for all four supported formats.
  Additional owner-editing cases cover doctor/clinic/hospital languages,
  inactive retention and clearing, legacy unknown classification, direct saves,
  rejection/resubmission/approval, explicit proposal resolution, immutable trips,
  unauthorized input, and approval-time schedule-conflict rollback.
- Frontend build passed. Focused provider portal, administrator comparisons,
  shared administrator form, and photo-review tests passed with at most two
  workers.
- `python scripts/check-provider-editing-browser.py` uses a disposable stable
  Chromium session with fail-closed synthetic API fixtures. It checks desktop,
  390px and 360px layouts, keyboard classification and image retry, local blob
  decoding, uploaded URL decoding, load-error recovery, explicit saves and
  reloads, structured names/languages and draft classification plus same-day
  independent visit locations.
- The existing photo-review and visits browser scripts also passed with
  synthetic fixtures, covering admin image review, approval/rejection,
  Previous/Current/Upcoming history, draft revision/removal and reload.
- Generated screenshots live under ignored `generated-artifacts/provider-editing`.
  The screenshot capture without fixture authentication could only see session
  verification; signed-in UI evidence comes from the isolated browser scripts,
  not from a real UAT account.
