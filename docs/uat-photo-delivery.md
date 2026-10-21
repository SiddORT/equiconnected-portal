# UAT photo delivery: blocked live repair and operator handoff

## Status and evidence (2026-10-21)

**UAT is not repaired. No live configuration was changed.**

At `2026-10-21 09:20:44 UTC`, an unauthenticated GET to:

```
https://uat.equiconnected.com/uploads/providers/00000000-0000-0000-0000-000000000000/photos/portal-routing-probe.png
```

returned HTTP **200**, `Content-Type: text/html`, `CF-Cache-Status: MISS`,
`Cache-Control: max-age=14400`. Its 2,235-byte body was the SPA entrypoint
(`<!doctype html>` and the root element), SHA-256
`d29d10d4fdfb1fcef692ba7fe2f626b67f268c39e07481e9fd47ea66eddfa93c`.
This establishes incorrect public routing, not which layer performed the rewrite.
A MISS does not rule out a CDN rewrite, Worker, or origin fallback.

A second public GET using the new checker at `2026-10-21 09:23:30 UTC` again
returned `200 text/html` (2,602 bytes, Cloudflare `EXPIRED`). Response sizes/cache
state can change; neither response was an image or a correct missing-file 404.
The checker exited 2 in diagnostic-only mode, with `passed: false` and an
explicit `HTML-200 routing failure`. Eight offline regression tests passed,
including a real local HTTP server exercising all four GETs; this does not
verify any deployed API origin.

The repository's `.github/workflows/deploy-uat.yml` connects to an external VPS
and invokes `scripts/deploy.sh` at
`/var/www/nodejs/uat.equiconnected.com`. That script reloads existing Nginx; it
does not install any `/uploads/` routing rule. No active Nginx/CDN configuration,
PM2 ecosystem file, verified upstream address, server access, or designated
existing synthetic UAT image was supplied. This workspace has neither that VPS
directory nor its Nginx configuration. Replit deployment metadata reports no
deployment for this fork; it cannot inspect the external VPS. GitHub Actions
secret references are not server access and were not retrieved.

**Required before an actual configuration can be matched and applied:**

1. An authorized UAT operator inspects the active vhost, inherited Nginx rules,
   actual `/api/` upstream and serving-instance inventory.
2. The operator identifies an already-existing, non-private synthetic image and
   computes its SHA-256. Do not invent a provider ID/file or upload anything for
   this step. Creating a synthetic asset/account requires separate permission.
3. Explicit approval for the specific Nginx/CDN edit, reload, and scoped purge.
   Task approval is not that authorization. No credentials should be posted in chat.

Until then the configuration below is an **operator-bound procedure, not a
verified patch for the active UAT server**. The port 8000 in local development
is not evidence of the VPS upstream. Exact screenshot-file presence,
readability, persistence, and instance consistency remain **unverified**; its
filename is unavailable. Profile saving does not repair missing or unreadable bytes.

## 1. Read-only discovery on the actual serving hosts

Use the operator's established administrative access. Do not run `deploy.sh`,
Git reset, migrations, PM2 reload, profile saves, or test uploads for this repair.
On each Nginx/API host:

```bash
# Inspect locally; full output may contain sensitive configuration.
sudo nginx -T 2>&1 | less
sudo ss -ltnp
ps -eo user,pid,args | grep '[u]vicorn'
```

In `nginx -T`, locate **the active TLS server for uat.equiconnected.com**, its
source file (Nginx prints source paths), and the effective `/api/` location.
Record locally the complete `proxy_pass`, referenced `upstream` definition,
API transport/port or Unix socket, Host/header requirements, HTTP version,
timeouts, TLS verification/SNI settings, and any included snippets.
Inspect server/http inherited rewrites, `try_files`, `error_page`,
`proxy_intercept_errors`, existing `/uploads` locations, regex image handlers,
and effective `client_max_body_size` on the upload API route. A server-level
rewrite executes before location selection and must explicitly exempt uploads.
Do not share unredacted dumps or PM2 environment output.

Inspect the running process's working directory and user without dumping its
environment; match the actual process, not merely the deployment checkout:

```bash
# Set PID from the actual UAT process found above (repeat for every instance).
: "${PID:?Set the actual UAT API PID}"
ps -o user=,pid=,args= -p "$PID"
sudo readlink -f "/proc/$PID/cwd"
```

Operator records: active vhost file, API upstream, API service user, actual
release path, uploads realpath/mount, all serving hosts/containers, CDN rules.
If these are unavailable, stop: do not substitute localhost:8000 or an IP
inferred from proxied public DNS.

## 2. Check storage separately, without changing it

The application mounts and writes `<running-backend>/uploads`. Use the actual
release's backend directory above; the documented checkout is only a candidate.
Choose the approved synthetic image's **relative storage reference** and
perform these read-only checks for every serving instance:

```bash
# Set these locally from actual inspection; do not paste private paths in evidence.
: "${UPLOADS_ROOT:?Absolute uploads directory used by the running API}"
: "${IMAGE_PATH:?Existing synthetic /uploads/providers/.../photos/... reference}"
: "${SERVICE_USER:?Actual API service user}"
FILE="$UPLOADS_ROOT/${IMAGE_PATH#/uploads/}"
sudo readlink -f "$UPLOADS_ROOT"
sudo namei -l "$FILE"
sudo stat --format='type=%F mode=%a owner=%U group=%G size=%s device=%d inode=%i' "$FILE"
findmnt -T "$UPLOADS_ROOT"
sudo -u "$SERVICE_USER" test -r "$FILE"
sudo -u "$SERVICE_USER" sha256sum "$FILE"
```

Use only canonical `/uploads/providers/<id>/photos/<filename>` references, no
`..`, URL, query string, or symlink escape. `namei` reveals parent traversal
permissions; `test -r` plus hashing as the API user establishes actual reads.
Keep raw filenames/output local if checking the screenshot's real file after
an authorized operator identifies it. Do not retrieve private image contents.
Do not chmod/chown, create directories, move files, delete, or reupload.

Inspect the deployment/release manager and mount configuration read-only.
Confirm that the running release and next release resolve uploads to the same
durable directory, and that deployment cleanup will not remove it. The checked-in
script's in-place reset does not prove persistent disk or shared-host storage.
Across separate hosts, compare synthetic file presence/hash and mount backing;
an identical path string does not mean shared storage. Repeat the GET check per
serving instance, not just through a load balancer. If instances have divergent
bytes, report that separately; do not mask it with CDN caching or affinity.

For historical file diagnosis, presence/readability and routing are independent:
origin 404 alone is not conclusive proof of missing bytes until the running
root, exact path and serving instance have been checked. Missing bytes require
separately authorized backup recovery, not saving a provider profile.

## 3. Bind the narrow correction to inspected configuration

**Approval gate:** present the exact candidate diff and affected UAT vhost/CDN
rules to the authorized operator. Obtain explicit server-change approval before
editing or reloading. No automated live patch is included here.

Within the existing UAT TLS server, add or amend only the `/uploads/` location.
The following command generates a local candidate snippet, **not a live edit**,
once the operator sets the actual upstream:

```bash
# Use the inspected API upstream authority, without an API URI suffix.
# Example shape only: http://existing_api_upstream (not a guessed port).
# If /api proxy_pass includes /api/ or another URI, retain ONLY its verified
# transport/authority for uploads. For Unix sockets or special TLS/header
# requirements, have the operator adapt the exact existing API configuration.
: "${VERIFIED_API_UPSTREAM:?Set the inspected API upstream, with no URI suffix}"
python - "$VERIFIED_API_UPSTREAM" <<'PY'
import sys
from urllib.parse import urlsplit
u = sys.argv[1]
p = urlsplit(u)
if (p.scheme not in ("http", "https") or not p.hostname or p.path
    or p.username or p.password or p.query or p.fragment
    or any(c in u for c in ' \t\r\n;{}$\\?#')):
    raise SystemExit("Refusing unsafe upstream or URI suffix; inspect/adapt manually.")
print("""location ^~ /uploads/ {
    # Preserve the entire /uploads/... URI: proxy_pass has NO URI suffix.
    proxy_pass %s;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_intercept_errors off;
}""" % u)
PY
```

Before use, retain **all required upstream-specific proxy settings** from the
existing API location (including any different Host, TLS/SNI, or headers).
Do not blindly copy an API-specific URI rewrite. This is a separate static GET
location: leave `/api/` and its upload POST and body-size limits untouched.
Preserve the existing application 10 MiB per-image limit and the proxy's existing
larger multipart allowance; do not add `client_max_body_size 0`.

The location must not include SPA `try_files`, URI stripping, `rewrite ... index.html`,
or HTML error interception. Preserve existing frontend fallback for other routes.
If `/uploads/` is already configured, amend it rather than adding a duplicate.
`^~` avoids regex static-image locations overriding this prefix, but does not
override server-level rewrites or a longer prefix/exact location: inspect those.

### CDN inspection and scoped changes

In the actual Cloudflare zone, inspect matching Workers/routes, Transform/URL
Rewrite Rules, Origin Rules, cache rules, custom error handling and any other
proxy between CDN and Nginx. Exempt **only this UAT host's `/uploads/*`** from SPA
rewrites/HTML interception; preserve unrelated routes, security and upload limits.
If needed, bypass caching for that path while validating, under explicit approval.
Do not enable broad cache-everything or cache HTML as images.

After origin and TLS-vhost checks pass, purge only affected upload URLs: the
synthetic image, missing probe and known affected photo URLs. If cached HTML is
widespread, use an approved host/path-scoped purge where available, never a
zone-wide purge by default. Changing rules is not a purge. Record original
rule definitions, ordering and matched scope for rollback. A missing probe
still returning HTML on a MISS means there is a remaining rewrite/fallback;
purging alone is not a repair.

## 4. Approved application, validation and rollback

Only the authorized operator performs these steps on the actual VPS:

```bash
: "${VHOST_FILE:?Set source file identified in nginx -T; resolve symlinks}"
# Preserve a protected backup OUTSIDE Nginx include directories.
BACKUP_DIR=$(sudo mktemp -d /root/uat-photo-routing.XXXXXX)
sudo cp -p -- "$VHOST_FILE" "$BACKUP_DIR/vhost.before"
sudoedit "$VHOST_FILE"  # apply only the reviewed uploads diff
sudo diff -u -- "$BACKUP_DIR/vhost.before" "$VHOST_FILE"
sudo nginx -t          # STOP on failure; do not reload
# Only after a passing test and the reviewed diff:
sudo systemctl reload nginx
sudo systemctl is-active nginx
```

If validation fails or delivery regresses, restore the saved vhost, validate
again, and reload only when validation passes:

```bash
sudo cp -p -- "$BACKUP_DIR/vhost.before" "$VHOST_FILE"
sudo nginx -t && sudo systemctl reload nginx
```

Retain and restore any other specifically changed include files too. Roll back
only changed CDN rules from saved definitions; repeat the scoped purge if needed.
Do not overwrite concurrent operator changes with an old backup: stop and
reconcile if the file changed outside the reviewed diff. No app restart,
redeployment, database migration or file mutation is required by the routing fix.

## 5. Reusable non-mutating delivery verification

Run from a trusted machine that can reach the origin. Python with Pillow is
required (already a project dependency); no application import or DB is used.
The checker performs anonymous GETs, refuses redirects and signed/auth URLs,
does not save bodies, and emits labels, statuses, MIME/decoding results,
synthetic SHA-256 and cache headers, not full URLs.

```bash
: "${API_ORIGIN_BASE:?Verified direct FastAPI HTTP(S) base; no /api suffix}"
: "${IMAGE_PATH:?Designated already-existing non-private synthetic storage path}"
: "${EXPECTED_SHA256:?Hash of that file read as the actual service user}"
python scripts/check-photo-delivery.py \
  --origin-base "$API_ORIGIN_BASE" \
  --public-base https://uat.equiconnected.com \
  --image-path "$IMAGE_PATH" --expected-sha256 "$EXPECTED_SHA256" \
  --synthetic-confirmed
```

Repeat `--origin-base` for every direct serving instance (labels are origin-1,
origin-2, etc.; maintain the endpoint inventory privately). For a Unix-socket
API, use the operator's existing authorized local tunnel/HTTP bridge, or inspect
with `curl --unix-socket` plus the same MIME/decoding/hash requirements; do not
change listener exposure merely for this test.

Also test the origin **TLS Nginx vhost without Cloudflare**, using the actual
origin address. This separates FastAPI, Nginx and CDN failures. Do not guess
the origin IP from Cloudflare public DNS. In a disposable operator shell:

```bash
set -euo pipefail
: "${VERIFIED_ORIGIN_IP:?Actual Nginx origin IP from the operator inventory}"
: "${IMAGE_PATH:?Designated existing non-private synthetic path}"
: "${EXPECTED_SHA256:?Service-user hash of that synthetic image}"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
EXISTING_STATUS=$(curl --silent --show-error --max-time 20 \
  --resolve "uat.equiconnected.com:443:$VERIFIED_ORIGIN_IP" \
  -D "$TMP/existing.headers" -o "$TMP/existing.body" -w '%{http_code}' \
  "https://uat.equiconnected.com$IMAGE_PATH")
test "$EXISTING_STATUS" = 200
python - "$TMP" "$EXPECTED_SHA256" <<'PY'
from email.parser import Parser
from pathlib import Path
from io import BytesIO
import hashlib, sys
from PIL import Image
root = Path(sys.argv[1])
# Last HTTP header block also handles an intervening proxy CONNECT response.
blocks = root.joinpath("existing.headers").read_text().strip().split("\n\n")
headers = Parser().parsestr("\n".join(blocks[-1].splitlines()[1:]))
body = root.joinpath("existing.body").read_bytes()
with Image.open(BytesIO(body)) as im:
    mime = Image.MIME[im.format]
    im.verify()
with Image.open(BytesIO(body)) as im:
    for frame in range(getattr(im, "n_frames", 1)):
        im.seek(frame)
        im.load()
assert headers.get_content_type() == mime, "Wrong image Content-Type"
assert hashlib.sha256(body).hexdigest() == sys.argv[2].lower(), "Wrong bytes"
print("Origin TLS vhost: decodable synthetic bytes and MIME match.")
PY
MISSING_STATUS=$(curl --silent --show-error --max-time 20 \
  --resolve "uat.equiconnected.com:443:$VERIFIED_ORIGIN_IP" \
  -o /dev/null -w '%{http_code}' \
  'https://uat.equiconnected.com/uploads/providers/00000000-0000-0000-0000-000000000000/photos/portal-routing-probe.png')
test "$MISSING_STATUS" = 404
```

No redirect following or disabled TLS verification is used. The temporary files
contain only the explicitly designated synthetic image and are removed on exit.

Exit 0 means all existing-image GETs returned 200, a supported MIME matching
the fully decoded image, bytes matching the on-disk synthetic baseline and
each other, and every missing-image GET returned 404. Exit 1 is failure.
It does not verify persistence or portal account behavior.

Without a synthetic baseline/origin, this diagnostic is useful but **cannot
pass full verification** (always exit 2, even if the missing route is correct):

```bash
python scripts/check-photo-delivery.py \
  --public-base https://uat.equiconnected.com --probe-missing-only
```

Offline checker regression tests:

```bash
python scripts/test-photo-delivery.py
```

These tests are **local checker evidence**, not UAT delivery evidence.
Existing FastAPI upload/static-serving tests also cannot establish VPS routing.

### Final evidence checklist

Record separately: local tests; each direct FastAPI instance; origin TLS vhost;
public UAT; service-user file reads; release persistence; serving-instance
consistency; CDN change/purge; and whether the exact screenshot file was identified.
Use only designated non-private synthetic hashes. Do not store private image
bytes, signed URLs, tokens, config secrets, or private storage references here.

The stored-image portal journey (select → explicit upload → save → reload →
stored URL decoding) needs separate authorization and an approved synthetic
account for writes/sign-in. No provider edits or admin decisions were performed.
Existing honest image-error/retry UI and strict reference validation remain
unchanged. Until the live checks pass, report **live repair/verification blocked**,
not “fixed locally” or “repaired by profile save.”
