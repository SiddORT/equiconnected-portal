"""Offline checker tests; no application startup, database, or UAT mutations."""
import argparse
import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from PIL import Image

spec = importlib.util.spec_from_file_location("photo_check", Path(__file__).with_name("check-photo-delivery.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def png(color="white", fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (2, 2), color).save(buf, format=fmt)
    return buf.getvalue()


class PhotoDeliveryTests(unittest.TestCase):
    def test_supported_formats_decode(self):
        for fmt, mime in check.MIMES.items():
            with self.subTest(fmt=fmt):
                body = png(fmt=fmt)
                self.assertEqual(check.inspect_response(
                    200, mime, body, missing=False,
                    expected_sha256=hashlib.sha256(body).hexdigest())["errors"], [])

    def test_html_200_and_missing_image_fail(self):
        for status, mime, body in [(200, "text/html", b"<!doctype html>"),
                                   (404, "application/json", b"{}")]:
            self.assertTrue(check.inspect_response(status, mime, body, missing=False)["errors"])
        self.assertTrue(check.inspect_response(200, "text/html", b"SPA", missing=True)["errors"])
        self.assertEqual(check.inspect_response(404, "text/html", b"not found", missing=True)["errors"], [])

    def test_bad_bytes_wrong_mime_hash_and_oversize_fail(self):
        for mime, body, digest in [
            ("image/png", b"invalid", None),
            ("image/jpeg", png(), None),
            ("image/png", png()[:-10], None),
            ("image/png", png(), "0" * 64),
            ("image/png", b"x" * (check.MAX_BYTES + 1), None),
        ]:
            self.assertTrue(check.inspect_response(
                200, mime, body, missing=False, expected_sha256=digest)["errors"])

    def test_unsafe_inputs_rejected(self):
        for url in ["https://user:secret@example.com", "https://example.com/?token=x",
                    "https://example.com/#x", "file:///tmp/x", "https://example.com/path",
                    "https://example.com:bad", "https://example.com?"]:
            with self.subTest(url=url), self.assertRaises(argparse.ArgumentTypeError):
                check.base_url(url)
        for path in [check.MISSING_PATH, "/uploads/../../secret", "https://example.com/photo.png"]:
            with self.assertRaises(argparse.ArgumentTypeError):
                check.image_path(path)

    def test_multiple_endpoints_compare_bytes_and_baseline(self):
        white, black = png(), png("black")
        def response(url, timeout):
            if url.endswith(check.MISSING_PATH):
                return 404, "application/json", b"{}", {}
            return 200, "image/png", black if url.startswith("http://public") else white, {}
        with patch.object(check, "fetch", side_effect=response):
            report = check.run_checks(
                [("origin-1", "http://origin"), ("public", "http://public")],
                "/synthetic.png", hashlib.sha256(white).hexdigest(), 2)
        self.assertFalse(report["passed"])
        self.assertIn("Origin/public image bytes differ.", report["errors"])
        self.assertEqual(len(report["results"]), 4)

    def test_valid_pair_and_diagnostic_never_claims_success(self):
        body = png()
        def response(url, timeout):
            return (404, "text/html", b"missing", {}) if url.endswith(check.MISSING_PATH) else (
                200, "image/png", body, {})
        with patch.object(check, "fetch", side_effect=response):
            endpoints = [("origin-1", "http://origin"), ("public", "http://public")]
            self.assertTrue(check.run_checks(
                endpoints, "/synthetic.png", hashlib.sha256(body).hexdigest(), 2)["passed"])
            self.assertFalse(check.run_checks(endpoints, None, None, 2)["passed"])

    def test_network_error_does_not_leak_url(self):
        with patch.object(check, "fetch", side_effect=OSError("https://private/token")):
            report = check.run_checks([("public", "https://public")], None, None, 2)
        self.assertNotIn("private", str(report))
        self.assertEqual(report["results"][0]["errors"], ["GET failed: OSError"])

    def test_real_http_get_and_redirect_refusal(self):
        calls = []
        body = png()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                status = 302 if self.path == "/redirect" else (
                    200 if self.path == "/synthetic.png" else 404)
                self.send_response(status)
                self.send_header("Content-Type", "image/png" if status == 200 else "text/html")
                if status == 302:
                    self.send_header("Location", "/must-not-follow")
                self.end_headers()
                self.wfile.write(body if status == 200 else b"missing")
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(check.fetch(base + "/missing", 2)[:3], (404, "text/html", b"missing"))
            self.assertEqual(check.fetch(base + "/redirect", 2)[0], 302)
            self.assertEqual(calls, ["/missing", "/redirect"])
            report = check.run_checks(
                [("local-test-origin", base), ("local-test-public", base)],
                "/synthetic.png", hashlib.sha256(body).hexdigest(), 2)
            self.assertTrue(report["passed"])
            self.assertEqual(calls[2:], [
                "/synthetic.png", check.MISSING_PATH, "/synthetic.png", check.MISSING_PATH])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
