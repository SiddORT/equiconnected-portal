"""Browser checks for member headers using non-production API fixtures.

Run with Chromium listening on CDP port 9222, the frontend running, and
REPLIT_DEV_DOMAIN available. No real credentials or email delivery are used.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets

ORIGIN = f"https://{os.environ['REPLIT_DEV_DOMAIN']}"
MEMBER = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "browser-fixture@example.test",
    "first_name": "Alexandria-Catherine-Elizabeth",
    "last_name": "Longname-Rider",
    "full_name": "Alexandria-Catherine-Elizabeth Longname-Rider",
    "role": "horse_owner",
    "roles": ["horse_owner"],
    "is_active": True,
    "email_verified_at": "2026-10-01T00:00:00Z",
    "last_successful_login_at": None,
}


class Browser:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0
        self.waiters = {}
        self.member = False
        self.errors = []
        self.api_paths = []

    async def receive(self):
        async for raw in self.socket:
            message = json.loads(raw)
            if "id" in message:
                future = self.waiters.pop(message["id"], None)
                if future:
                    if "error" in message:
                        future.set_exception(RuntimeError(message["error"]))
                    else:
                        future.set_result(message.get("result", {}))
            elif message.get("method") == "Fetch.requestPaused":
                asyncio.create_task(self.fixture(message["params"]))
            elif message.get("method") == "Runtime.exceptionThrown":
                details = message["params"]["exceptionDetails"]
                self.errors.append(details.get("exception", {}).get("description", details.get("text")))

    async def send(self, method, params=None):
        self.sequence += 1
        future = asyncio.get_running_loop().create_future()
        self.waiters[self.sequence] = future
        await self.socket.send(json.dumps({
            "id": self.sequence, "method": method, "params": params or {},
        }))
        return await asyncio.wait_for(future, 20)

    async def fixture(self, params):
        path = urlparse(params["request"]["url"]).path
        if not path.startswith("/api/v1/"):
            await self.send("Fetch.continueRequest", {"requestId": params["requestId"]})
            return
        self.api_paths.append(path)
        status = 200
        if path.endswith("/auth/refresh"):
            status = 200 if self.member else 401
            data = {"access_token": "browser-fixture", "user": MEMBER} if self.member else {"detail": "Unauthenticated"}
        elif path.endswith("/system-settings"):
            data = {"timezone": "UTC", "date_format": "DD/MM/YYYY", "time_format": "24h"}
        elif path.endswith("/profile"):
            data = {"user": MEMBER, "horses": [], "phones": [], "addresses": []}
        elif path.endswith("/member/history/recent"):
            data = []
        elif path.endswith("/member/history"):
            data = {"data": [], "meta": {"page": 1, "page_size": 20, "total": 0, "total_pages": 0}}
        elif path.endswith("/messages/unread"):
            data = {"count": 3}
        elif path.endswith("/member/providers"):
            data = {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}
        elif "/member-password-recovery/" in path:
            data = {"message": "If eligible, a recovery email will arrive."}
        elif any(part in path for part in ("languages", "specializations", "regions", "filter-options")):
            data = []
        else:
            data = {"message": "Fixture"}
        await self.send("Fetch.fulfillRequest", {
            "requestId": params["requestId"], "responseCode": status,
            "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
            "body": base64.b64encode(json.dumps(data).encode()).decode(),
        })

    async def js(self, expression):
        result = await self.send("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True,
        })
        if "exceptionDetails" in result:
            raise AssertionError(result["exceptionDetails"])
        return result["result"].get("value")

    async def wait(self, expression):
        for _ in range(80):
            if await self.js(expression):
                return
            await asyncio.sleep(.1)
        raise AssertionError(f"Browser condition did not become true: {expression}")

    async def navigate(self, path):
        await self.send("Page.navigate", {"url": ORIGIN + path})
        await asyncio.sleep(2)

    async def screenshot(self, name):
        await asyncio.sleep(.3)  # Wait for dropdown entrance animation, not a transitional frame.
        output = await self.send("Page.captureScreenshot", {"format": "jpeg"})
        Path("/tmp/task352-visual").mkdir(exist_ok=True)
        Path(f"/tmp/task352-visual/{name}.jpg").write_bytes(base64.b64decode(output["data"]))


async def main():
    targets = json.load(urlopen("http://127.0.0.1:9222/json"))
    page = next(target for target in targets if target["type"] == "page")
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=20_000_000) as socket:
        browser = Browser(socket)
        receive = asyncio.create_task(browser.receive())
        await browser.send("Page.enable")
        await browser.send("Runtime.enable")
        await browser.send("Fetch.enable", {"patterns": [{"urlPattern": ORIGIN + "/api/v1/*"}]})
        for member in (False, True):
            browser.member = member
            for width in (1440, 390, 320):
                await browser.send("Emulation.setDeviceMetricsOverride", {
                    "width": width, "height": 850, "deviceScaleFactor": 1,
                    "mobile": width < 500,
                })
                await browser.navigate("/")
                await browser.wait("!!document.querySelector('header nav')")
                assert await browser.js("innerWidth") == width
                assert await browser.js("document.documentElement.scrollWidth <= innerWidth")
                if member:
                    await browser.wait("!!document.querySelector('button[aria-label^=\"Account menu for\"]')")
                    check = await browser.js("""(() => {
                      const trigger = document.querySelector('button[aria-label^="Account menu for"]');
                      const bounds = trigger.getBoundingClientRect();
                      return {visible: bounds.width > 30 && bounds.left >= 0 && bounds.right <= innerWidth,
                        text: trigger.innerText, rightmost: trigger.closest('header').querySelectorAll('button')[0] !== trigger};
                    })()""")
                    assert check["visible"] and "Alexandria" in check["text"], check
                    if width > 1000:
                        assert await browser.js("""(() => {
                          const directory = [...document.querySelectorAll('header a')].find(a=>a.textContent==='Directory');
                          const account = document.querySelector('button[aria-label^="Account menu for"]');
                          return directory.getBoundingClientRect().right <= account.getBoundingClientRect().left;
                        })()""")
                    await browser.js("document.querySelector('button[aria-label^=\"Account menu for\"]').click()")
                    await browser.wait("document.querySelector('[role=\"menu\"]')?.innerText.includes('Reset password')")
                    assert await browser.js("""(() => {const r=document.querySelector('[role="menu"]').getBoundingClientRect();
                      return r.left>=0 && r.right<=innerWidth;})()""")
                    await browser.screenshot(f"member-home-{width}")
                    await browser.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "End", "code": "End"})
                    assert await browser.js("document.activeElement.innerText") == "Sign out"
                    await browser.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
                    assert await browser.js("!document.querySelector('[role=\"menu\"]')")
                else:
                    assert await browser.js("!document.querySelector('button[aria-label^=\"Account menu for\"]')")
                    await browser.screenshot(f"guest-home-{width}")
                print(f"PASS homepage {'member' if member else 'guest'} at {width}px")
        browser.member = True
        for width in (1440, 390, 320):
            await browser.send("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 568 if width == 320 else 850, "deviceScaleFactor": 1, "mobile": width < 500,
            })
            await browser.navigate("/history")
            await browser.wait("!!document.querySelector('button[aria-label^=\"Account menu for\"]')")
            await browser.js("document.querySelector('button[aria-label^=\"Account menu for\"]').click()")
            await browser.wait("!!document.querySelector('[role=\"menu\"]')")
            assert await browser.js("""(() => {
              const menu=document.querySelector('[role="menu"]').getBoundingClientRect();
              const button=document.querySelector('button[aria-label^="Account menu for"]');
              const identity=button.querySelector('strong');
              return identity.getBoundingClientRect().width > 0 && menu.left>=0 && menu.right<=innerWidth && menu.bottom<=innerHeight
                && document.documentElement.scrollWidth<=innerWidth
                && !document.querySelector('button[aria-label="Logout"]')
                && !!document.querySelector('header a[href="/member/messages"]')
                && ['Profile','Reset password','Sign out'].every(text=>[...document.querySelectorAll('[role="menuitem"]')].some(i=>i.innerText.includes(text)));
            })()""")
            await browser.screenshot(f"member-space-{width}")
            print(f"PASS member-space at {width}px")
        browser.member = False
        await browser.navigate("/reset-password#token=browser-fixture-not-real")
        await browser.wait("document.querySelector('#member-new-password') !== null")
        assert await browser.js("location.hash + location.search") == ""
        assert await browser.js("document.querySelector('meta[name=\"referrer\"]').content") == "no-referrer"
        await browser.screenshot("recovery-mobile")
        assert not browser.errors, browser.errors
        print("PASS recovery URL/referrer and no uncaught browser exceptions")
        receive.cancel()


if __name__ == "__main__":
    asyncio.run(main())