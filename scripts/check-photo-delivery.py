#!/usr/bin/env python3
"""Read-only synthetic photo GET checks. Never prints URLs, bodies or credentials."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import re
import warnings
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from PIL import Image

MISSING_PATH = (
    "/uploads/providers/00000000-0000-0000-0000-000000000000/"
    "photos/portal-routing-probe.png"
)
MAX_BYTES = 10 * 1024 * 1024
MIMES = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def base_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme in ("http", "https") and parts.hostname and parts.port != 0
            and not parts.username and not parts.password
            and parts.path in ("", "/") and not parts.query and not parts.fragment
            and not re.search(r"[\s\\?#]", value)
        )
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("Use a bare HTTP(S) base URL without credentials or query.")
    return value.rstrip("/")


def image_path(value: str) -> str:
    if not re.fullmatch(
        r"/uploads/providers/[0-9a-fA-F-]{36}/photos/[A-Za-z0-9_-]+\.(?:png|jpe?g|gif|webp)",
        value,
        re.IGNORECASE,
    ) or value == MISSING_PATH:
        raise argparse.ArgumentTypeError("Use a designated synthetic provider image path, not a URL.")
    return value


def fetch(url: str, timeout: float) -> tuple[int, str, bytes, dict]:
    # No redirects, cookies, auth, environment proxies, retries or cache mutation.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(url, headers={"User-Agent": "EquiConnected-photo-delivery-check/1"})
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(MAX_BYTES + 1)
        return response.status, response.headers.get_content_type(), body, {
            key: response.headers.get(key)
            for key in ("CF-Cache-Status", "Age", "Cache-Control")
            if response.headers.get(key) is not None
        }


def inspect_response(status: int, mime: str, body: bytes, *, missing: bool,
                     expected_sha256: str | None = None) -> dict:
    result = {"status": status, "content_type": mime, "byte_count": len(body), "errors": []}
    errors = result["errors"]
    if missing:
        if status != 404:
            errors.append("Missing image must return 404, not SPA fallback or redirect.")
        if status == 200 and mime in ("text/html", "application/xhtml+xml"):
            errors.append("HTML-200 routing failure.")
        return result
    if status != 200:
        errors.append("Expected synthetic image is unavailable (requires 200).")
    if mime not in MIMES.values():
        errors.append("Expected a supported image Content-Type; HTML is not an image.")
    if len(body) > MAX_BYTES:
        errors.append("Response exceeds the 10 MiB image limit.")
    if errors:
        return result
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body)) as image:
                if MIMES.get(image.format) != mime:
                    raise ValueError("MIME mismatch")
                image.verify()
            with Image.open(BytesIO(body)) as image:
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    image.load()
                result["format"] = image.format
                result["dimensions"] = list(image.size)
    except Exception:
        errors.append("Image decoding failed or decoded format disagrees with Content-Type.")
        return result
    result["sha256"] = hashlib.sha256(body).hexdigest()
    if expected_sha256 and result["sha256"] != expected_sha256:
        errors.append("Bytes differ from the designated synthetic file SHA-256.")
    return result


def run_checks(endpoints: list[tuple[str, str]], path: str | None, digest: str | None,
               timeout: float) -> dict:
    rows = []
    for label, base in endpoints:
        for kind, target in ([("existing", path)] if path else []) + [("missing", MISSING_PATH)]:
            try:
                status, mime, body, cache = fetch(base + target, timeout)
                row = inspect_response(status, mime, body, missing=kind == "missing",
                                       expected_sha256=digest)
                row["cache"] = cache
            except Exception as exc:
                # Exception messages can include full URLs; retain only the type.
                row = {"errors": ["GET failed: " + type(exc).__name__]}
            rows.append({"endpoint": label, "check": kind, **row})
    hashes = {row["sha256"] for row in rows if "sha256" in row}
    errors = ["Origin/public image bytes differ."] if len(hashes) > 1 else []
    probe_only = path is None
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "missing-only diagnostic; NOT full delivery verification" if probe_only else "delivery",
        "passed": not probe_only and not errors and all(not row["errors"] for row in rows),
        "errors": errors,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-base", type=base_url, required=True)
    parser.add_argument("--origin-base", type=base_url, action="append", default=[],
                        help="Repeat for every actual API serving instance.")
    parser.add_argument("--image-path", type=image_path)
    parser.add_argument("--expected-sha256", help="SHA-256 of the designated existing synthetic file.")
    parser.add_argument("--synthetic-confirmed", action="store_true",
                        help="Confirm this image is non-private and authorized for read-only checks.")
    parser.add_argument("--probe-missing-only", action="store_true",
                        help="Diagnostic only; exit 2 even if the missing probe correctly returns 404.")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if not 0 < args.timeout <= 120:
        parser.error("Timeout must be between 0 and 120 seconds.")
    if args.probe_missing_only:
        if args.image_path or args.expected_sha256:
            parser.error("Missing-only mode cannot verify an existing image.")
    elif not (
        args.origin_base and args.image_path and args.synthetic_confirmed
        and re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_sha256 or "")
    ):
        parser.error("Full check requires origin, image path, expected SHA-256 and synthetic confirmation.")
    endpoints = [(f"origin-{i}", base) for i, base in enumerate(args.origin_base, 1)]
    endpoints.append(("public", args.public_base))
    report = run_checks(endpoints, args.image_path,
                        args.expected_sha256.lower() if args.expected_sha256 else None, args.timeout)
    print(json.dumps(report, indent=2))
    return 2 if args.probe_missing_only else (0 if report["passed"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
