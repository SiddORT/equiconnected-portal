"""Opt-in real browser → isolated FastAPI → PostgreSQL → admin UI round trip.

RUN_PROVIDER_BROWSER=1 python -m pytest tests/test_provider_direct_browser.py -q
All API traffic is intercepted and served by the pytest TestClient/schema.
Unknown requests fail closed. No real credentials, notifications or live writes.
"""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest

from app.core.security import create_access_token
from app.models.enums import PublicationStatus
from tests.test_provider_profile_updates import _portal_provider

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("direct_browser_helpers", ROOT / "scripts/check-provider-insights-browser.py")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


@pytest.mark.skipif(os.environ.get("RUN_PROVIDER_BROWSER") != "1", reason="Opt-in isolated browser check")
def test_desktop_mobile_owner_save_then_real_admin_read(client, db, seeded_admin):
    admin, _ = seeded_admin
    provider, account = _portal_provider(db, admin, email="browser-owner@synthetic.example.com",
        name="Synthetic cross-portal clinic", publication_status=PublicationStatus.PUBLISHED)
    provider_id = str(provider.id)
    tokens = {
        "provider": create_access_token(account.id),
        "admin": create_access_token(admin.id),
    }
    # Seed helpers return canonical owned rows; all subsequent writes go through
    # real API validation and persistence, not an in-memory browser response mock.
    host = f"https://{os.environ['REPLIT_DEV_DOMAIN']}"
    output = ROOT / "generated-artifacts/provider-direct-save"
    output.mkdir(parents=True, exist_ok=True)
    executables = list(Path("/home/runner/.cache/ms-playwright").glob("chromium-*/chrome-linux/chrome"))
    executable = os.environ.get("CHROMIUM_BIN") or (str(executables[0]) if executables else shutil.which("chromium"))
    assert executable, "Chromium is required for the opt-in browser check."
    # Chromium child processes can briefly finish writing their disposable
    # profile after the parent exits. Cleanup must not replace test assertions.
    with tempfile.TemporaryDirectory(prefix="provider-direct-browser-", ignore_cleanup_errors=True) as temporary:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        process = subprocess.Popen([executable, "--headless", "--no-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu", f"--remote-debugging-port={port}",
            f"--user-data-dir={temporary}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        async def exercise():
            for _ in range(100):
                try:
                    targets = json.load(urlopen(f"http://127.0.0.1:{port}/json", timeout=1))
                    target = next(item for item in targets if item["type"] == "page")
                    break
                except (OSError, StopIteration):
                    await asyncio.sleep(.1)
            else:
                raise AssertionError("Chromium did not start")
            browser = helpers.Browser(target["webSocketDebuggerUrl"])
            await browser.connect()
            state = {"role": "provider", "unknown": [], "saves": 0, "admin_reads": 0}

            async def intercept(params):
                request, request_id = params["request"], params["requestId"]
                parsed = urlparse(request["url"])
                path, method = parsed.path, request["method"]
                if not path.startswith("/api/"):
                    if parsed.netloc == urlparse(host).netloc and path.startswith(("/src/", "/node_modules/")):
                        await browser.call("Fetch.continueRequest", {"requestId": request_id})
                        return
                    state["unknown"].append(f"{method} {path}")
                    await browser.call("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
                    return
                status = 200
                if path == "/api/v1/auth/refresh":
                    user = client.get("/api/v1/auth/me",
                        headers={"Authorization": f"Bearer {tokens[state['role']]}"}).json()
                    body = {"access_token": tokens[state["role"]], "token_type": "bearer",
                            "expires_in": 900, "user": user}
                elif path == "/api/v1/messages/unread":
                    body = {"count": 0}
                elif path == "/api/v1/system-settings":
                    body = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
                elif (
                    (path == "/api/v1/auth/me" and method == "GET")
                    or (path in ("/api/v1/provider/portal/profile", "/api/v1/provider/portal/specializations") and method in ("GET", "PATCH"))
                    or (path in (f"/api/v1/admin/providers/{provider_id}", f"/api/v1/admin/providers/{provider_id}/portal-access", "/api/v1/admin/specializations") and method == "GET")
                ):
                    response = client.request(method, path + ("?" + parsed.query if parsed.query else ""),
                        headers={"Authorization": f"Bearer {tokens[state['role']]}"},
                        json=json.loads(request["postData"]) if request.get("postData") else None)
                    status, body = response.status_code, response.json()
                    if status != 200:
                        print("Synthetic API failure:", method, path, status, body)
                    if method == "PATCH":
                        state["saves"] += 1
                        assert body["profile_update"] is None
                    if path == f"/api/v1/admin/providers/{provider_id}":
                        state["admin_reads"] += 1
                else:
                    state["unknown"].append(f"{method} {path}")
                    status, body = 599, {"error": {"code": "synthetic_unexpected_request"}}
                await browser.call("Fetch.fulfillRequest", {"requestId": request_id,
                    "responseCode": status, "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                    "body": base64.b64encode(json.dumps(body).encode()).decode()})

            browser.fetch_handler = intercept
            try:
                await browser.call("Page.enable")
                await browser.call("Runtime.enable")
                await browser.call("Network.enable")
                await browser.call("Network.setCacheDisabled", {"cacheDisabled": True})
                await browser.call("Fetch.enable", {"patterns": [{"urlPattern": "*/api/*"}]})
                for width in (1440, 390):
                    state["role"] = "provider"
                    await browser.call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 950, "deviceScaleFactor": 1, "mobile": width < 500})
                    await browser.call("Page.navigate", {"url": host + "/provider/account"})
                    await browser.wait_for("!!document.querySelector('#portal-name')", "real provider form")
                    name = f"Synthetic saved clinic {width}"
                    await browser.set_value("#portal-name", name)
                    await browser.click_text("Save profile")
                    await browser.wait_for("document.body.innerText.includes('No further approval is needed') || !!document.querySelector('[role=alert]')", "save response")
                    assert await browser.evaluate("document.body.innerText.includes('No further approval is needed')"), await browser.evaluate("document.body.innerText")
                    assert await browser.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    shot = await browser.call("Page.captureScreenshot", {"format": "png"})
                    (output / f"provider-{width}.png").write_bytes(base64.b64decode(shot["data"]))
                    await browser.call("Page.reload")
                    await browser.wait_for(f"document.querySelector('#portal-name')?.value === {json.dumps(name)}", "persisted owner reload")
                    state["role"] = "admin"
                    await browser.call("Page.navigate", {"url": host + f"/admin/providers/{provider_id}"})
                    await browser.wait_for(f"document.body.innerText.includes({json.dumps(name)})", "canonical administrator detail")
                    shot = await browser.call("Page.captureScreenshot", {"format": "png"})
                    (output / f"admin-{width}.png").write_bytes(base64.b64decode(shot["data"]))
                assert state["saves"] == 2 and state["admin_reads"] >= 2
                assert not state["unknown"], state["unknown"]
                assert not browser.background_errors, browser.background_errors
                assert not browser.page_errors, browser.page_errors
            finally:
                await browser.close()

        try:
            asyncio.run(exercise())
        finally:
            process.terminate()
            process.wait(timeout=10)
