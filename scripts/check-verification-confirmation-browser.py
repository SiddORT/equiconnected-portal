"""Check the shipped provider confirmation with synthetic, fail-closed API fixtures.

Start the Frontend workflow, then run python scripts/check-verification-confirmation-browser.py.
No account is created, no application is decided, and no email is sent.
Screenshots are temporary evidence under /tmp/verification-confirmation-browser.
"""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "provider_access_browser", ROOT / "scripts/check-provider-access-browser.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ORIGIN = "http://127.0.0.1:5000"
MESSAGE = (
    "Your email has been verified. Your account is awaiting administrator approval. "
    "Once approved, you’ll receive an email with a link to sign in."
)
OUT = Path("/tmp/verification-confirmation-browser")


async def run():
    bundled = sorted(Path("/nix/store").glob("*playwright-chromium-cjk-*/chrome-linux/chrome"))
    chromium = os.environ.get("CHROMIUM_BIN") or (
        str(bundled[0]) if bundled else "/repl/tools/bin/chromium"
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verification-browser-") as profile:
        with (OUT / "chromium.log").open("w") as log:
            process = subprocess.Popen([
                chromium, "--headless", "--no-sandbox", "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank",
            ], stdout=log, stderr=log)
            browser = None
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Chromium exited; see chromium.log")
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/json", timeout=.5) as response:
                            targets = json.load(response)
                        target = next(item for item in targets if item["type"] == "page")
                        break
                    except (OSError, ValueError, StopIteration):
                        await asyncio.sleep(.1)
                else:
                    raise RuntimeError("Chromium did not start")
                browser = module.Browser(target["webSocketDebuggerUrl"])
                await browser.connect()
                failures = []
                redemptions = []

                async def intercept(params):
                    request = params["request"]
                    parsed = urlsplit(request["url"])
                    try:
                        if not parsed.path.startswith("/api/"):
                            if request["url"].startswith(ORIGIN + "/"):
                                await browser.call("Fetch.continueRequest", {"requestId": params["requestId"]})
                                return
                            # External fonts are unnecessary for isolated checks.
                            if params.get("resourceType") == "Stylesheet":
                                await browser.call("Fetch.fulfillRequest", {
                                    "requestId": params["requestId"], "responseCode": 200, "body": "",
                                })
                                return
                            raise AssertionError("Non-local request blocked")
                        key = (request["method"], parsed.path)
                        if key == ("POST", "/api/v1/auth/verify-email"):
                            redemptions.append(json.loads(request.get("postData", "{}")))
                            data, status = {
                                "email": "synthetic.provider@example.test",
                                "message": MESSAGE,
                                "outcome": "provider_awaiting_approval",
                            }, 200
                        elif key == ("POST", "/api/v1/auth/refresh"):
                            data, status = {"detail": "No synthetic session"}, 401
                        elif key == ("GET", "/api/v1/system-settings"):
                            data, status = {
                                "timezone": "UTC", "date_format": "month_day_year", "time_format": "24_hour",
                            }, 200
                        else:
                            raise AssertionError(f"Unmatched API fixture: {key}")
                        await browser.call("Fetch.fulfillRequest", {
                            "requestId": params["requestId"], "responseCode": status,
                            "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                            "body": base64.b64encode(json.dumps(data).encode()).decode(),
                        })
                    except Exception as error:
                        failures.append(str(error))
                        await browser.call("Fetch.failRequest", {
                            "requestId": params["requestId"], "errorReason": "BlockedByClient",
                        })

                browser.handlers.append(intercept)
                await browser.call("Page.enable")
                await browser.call("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
                for width, height, mobile in [(1440, 1000, False), (390, 844, True)]:
                    await browser.call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile,
                    })
                    count_before = len(redemptions)
                    token = f"synthetic-provider-verification-{width}"
                    await browser.call("Page.navigate", {"url": f"{ORIGIN}/verify-email?token={token}"})
                    await browser.wait_for(
                        "document.body.innerText.includes('Email verified successfully')",
                        "provider confirmation",
                    )
                    await asyncio.sleep(2.5)  # Beyond the old 1.8-second redirect.
                    result = await browser.evaluate("""(() => ({
                        path: location.pathname, search: location.search,
                        text: document.body.innerText,
                        links: [...document.querySelectorAll('a')].map(a => ({text: a.textContent, href: a.getAttribute('href')})),
                        overflow: document.documentElement.scrollWidth > innerWidth,
                        progress: [...document.querySelectorAll('*')].some(e => /redirectProgress/.test(getComputedStyle(e).animationName))
                    }))()""")
                    assert result["path"] == "/verify-email" and result["search"] == "", result
                    assert MESSAGE in result["text"] and "Redirecting" not in result["text"], result
                    assert {"text": "Return to EquiConnected", "href": "/"} in result["links"], result
                    assert not any(link["href"] in ("/login", "/provider/login") for link in result["links"]), result
                    assert not result["overflow"] and not result["progress"], result
                    assert redemptions[count_before:] == [{"token": token}], redemptions
                    assert not failures, failures
                    shot = await browser.call("Page.captureScreenshot", {"format": "png"})
                    path = OUT / f"provider-confirmation-{width}.png"
                    path.write_bytes(base64.b64decode(shot["data"]))
                    print(f"PASS: persistent confirmation, single redemption, token removal, no redirect/progress/overflow at {width}px: {path}")
            finally:
                if browser:
                    await browser.close()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(run())
