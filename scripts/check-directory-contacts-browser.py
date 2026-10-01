"""Read-only live directory check. Session credentials stay in process memory.

Run from backend with PYTHONPATH=. python ../scripts/check-directory-contacts-browser.py
after starting Chromium with --remote-debugging-port=9222.
Only session restoration and one deliberate directory failure are intercepted;
directory, filter, saved-provider and profile requests use the running backend.
"""
import asyncio
import base64
import json
import os
import ssl
from urllib.request import urlopen

import httpx
import websockets
from sqlalchemy import select

from app.db.base import Base  # noqa: F401 — register all ORM relationships
from app.db.session import SessionLocal
from app.core.security import create_access_token
from app.models.user import PUBLIC_ACCOUNT_ROLE_NAMES, User


async def main():
    with SessionLocal() as db:
        users = db.scalars(select(User).where(
            User.email_verified_at.is_not(None), User.is_active.is_(True),
        )).all()
        member = next(user for user in users if {
            user.role.name, *(assignment.role.name for assignment in user.role_assignments),
        }.intersection(PUBLIC_ACCOUNT_ROLE_NAMES))
        token = create_access_token(subject=member.id)
    origin = "https://" + os.environ["REPLIT_DEV_DOMAIN"]
    with httpx.Client(base_url=origin, verify=ssl.create_default_context()) as client:
        user_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        user_response.raise_for_status()
        session = {"access_token": token, "user": user_response.json()}
    target = json.load(urlopen("http://127.0.0.1:9222/json"))[0]
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
        pending = {}
        counter = 0
        fail_directory = True
        responses = []

        async def command(method, params=None):
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            result = await future
            if "error" in result:
                raise RuntimeError(result["error"]["message"])
            return result.get("result", {})

        async def intercept(params):
            nonlocal fail_directory
            url = params["request"]["url"]
            if "/auth/refresh" in url:
                status, data = 200, session
            elif fail_directory and url.split("?")[0].endswith("/member/providers"):
                status, data = 503, {"detail": {"message": "Deliberate browser retry check"}}
            else:
                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            await command("Fetch.fulfillRequest", {
                "requestId": params["requestId"], "responseCode": status,
                "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                "body": base64.b64encode(json.dumps(data).encode()).decode(),
            })

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    pending.pop(message["id"]).set_result(message)
                elif message.get("method") == "Fetch.requestPaused":
                    asyncio.create_task(intercept(message["params"]))
                elif message.get("method") == "Network.responseReceived":
                    response = message["params"]["response"]
                    if "/member/providers" in response["url"]:
                        responses.append((response["url"], response["status"]))

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command("Runtime.evaluate", {
                "expression": expression, "returnByValue": True, "awaitPromise": True,
            })
            if "exceptionDetails" in result:
                raise RuntimeError("Browser expression failed")
            return result["result"].get("value")

        async def wait_for(expression):
            for _ in range(100):
                if await evaluate(expression):
                    return
                await asyncio.sleep(.1)
            raise AssertionError("Timed out: " + expression)

        async def click(text):
            await evaluate(f"[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==={json.dumps(text)}).click()")

        await command("Page.enable")
        await command("Network.enable")
        await command("Fetch.enable", {"patterns": [{"urlPattern": "*/api/v1/*"}]})
        await command("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
        })
        await command("Page.navigate", {"url": origin + "/providers"})
        await wait_for("document.body.textContent.includes('Results unavailable')")
        # Strict Mode may replay the initial load: fail until the explicit retry.
        fail_directory = False
        responses.clear()
        await click("Try Again")
        await wait_for("!!document.querySelector('a[href*=\"#contact\"]')")
        assert not await evaluate("document.body.textContent.includes('Results unavailable')")
        print("PASS: genuine error state and Try Again recover to live provider cards")
        screenshot = await command("Page.captureScreenshot", {"format": "jpeg"})
        with open("/tmp/directory-contact-recovery.jpg", "wb") as image:
            image.write(base64.b64decode(screenshot["data"]))
        link = await evaluate("document.querySelector('a[href*=\"#contact\"]').getAttribute('href')")
        await command("Page.navigate", {"url": origin + link})
        await wait_for("!!document.querySelector('#contact a[href^=\"tel:\"]')")
        assert await evaluate("document.querySelector('#contact a[href^=\"tel:\"]').textContent.includes('+')")
        assert await evaluate("!!document.querySelector('#contact a[href^=\"mailto:\"]')")
        print("PASS: live profile displays calling code, phone and email")
        await command("Page.navigate", {"url": origin + "/providers?provider_type=DOCTOR"})
        await wait_for("!!document.querySelector('a[href*=\"#contact\"]')")
        print("PASS: filtered directory loads live cards")
        await click("Saved providers")
        await wait_for("document.querySelector('h1')?.textContent === 'Saved providers' && !document.body.textContent.includes('Finding providers')")
        await wait_for("!document.querySelector('[aria-busy=\"true\"]')")
        assert not await evaluate("document.body.textContent.includes('Results unavailable')")
        print("PASS: saved-provider view loads without contact serialization errors")
        assert all(status < 400 for url, status in responses), responses
        print("PASS: live directory, filter and detail requests succeed")
        reader.cancel()


if __name__ == "__main__":
    asyncio.run(main())