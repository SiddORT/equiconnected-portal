"""Browser-only fixture check; never changes persisted application data."""
import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.request import urlopen

import websockets


async def main():
    target = json.load(urlopen("http://127.0.0.1:9222/json"))[0]
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
        pending = {}
        counter = 0
        application = {
            "id": "browser-application", "user_id": "browser-user", "provider_id": None,
            "provider_type": "CLINIC", "provider_name": "Meadow Equine Referral and Rehabilitation Clinic",
            "visit_stability": "STABLE_VISIT", "review_status": "PENDING_REVIEW",
            "first_name": "Amina", "last_name": "Rider", "full_name": "Amina Rider",
            "email": "review-fixture@example.com", "mobile_number": "+971 50 123 4567",
            "professional_title": "Equine veterinarian", "years_experience": 0,
            "specialization_ids": ["s1", "s2", "s3"],
            "specializations": [{"id": "s1", "name": "Equine internal medicine"},
                                {"id": "s2", "name": "Sports medicine and rehabilitation"},
                                {"id": "s3", "name": "Dentistry"}],
            "languages": [{"id": "l1", "name": "English"}, {"id": "l2", "name": "Arabic"}],
            "working_address": "Building 12, Suite 405, Meadow Equine Medical Campus, Longhorn Avenue, near the eastern stable entrance and rehabilitation paddock",
            "postal_code": "78701", "city": "Austin", "state_province": "Texas",
            "country": "United States", "stable_visit": False,
            "maximum_working_radius_km": None, "emergency_services_available": False,
            "emergency_contact_number": None, "terms_accepted_at": "2026-08-20T08:15:00Z",
            "privacy_accepted_at": "2026-08-20T08:16:00Z",
            "email_verified_at": "2026-08-21T12:00:00Z", "reviewed_by_user_id": None,
            "reviewed_by_name": None, "reviewed_at": None, "rejection_reason": None,
            "created_at": "2026-08-20T08:16:00Z",
        }

        async def command(method, params=None):
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            result = await future
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})

        async def intercept(params):
            url = params["request"]["url"]
            if "/auth/refresh" in url:
                data = {"access_token": "browser-only-fixture", "user": {
                    "id": "browser-admin", "email": "reviewer@example.com", "full_name": "Browser reviewer",
                    "first_name": "Browser", "last_name": "Reviewer", "role": "admin",
                    "roles": ["admin"], "is_active": True, "email_verified_at": application["email_verified_at"],
                }}
            elif "/system-settings" in url:
                data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
            elif "/provider-applications" in url:
                if url.endswith("/approve") or url.endswith("/reject"):
                    approved = url.endswith("/approve")
                    application.update(review_status="APPROVED" if approved else "REJECTED",
                                       provider_id="browser-listing" if approved else None,
                                       reviewed_by_name="Browser reviewer", reviewed_by_user_id="browser-admin",
                                       reviewed_at="2026-10-01T05:00:00Z",
                                       rejection_reason=None if approved else "Browser rejection feedback")
                    data = application
                else:
                    data = {"data": [application], "meta": {"page": 1, "page_size": 10, "total": 1, "total_pages": 1}}
            else:
                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            await command("Fetch.fulfillRequest", {
                "requestId": params["requestId"], "responseCode": 200,
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

        reader = asyncio.create_task(receive())
        async def evaluate(expression):
            result = await command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result["result"].get("value")

        async def click(text):
            assert await evaluate(
                f"(() => {{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==={json.dumps(text)}); if(!b)return false; b.click(); return true;}})()"
            ), text
            await asyncio.sleep(.3)

        await command("Page.enable")
        await command("Fetch.enable", {"patterns": [{"urlPattern": "*/api/v1/*"}]})
        await command("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": "https://" + os.environ["REPLIT_DEV_DOMAIN"] + "/admin/provider-applications"})
        await asyncio.sleep(4)
        assert await evaluate("!!document.querySelector('[aria-label=\"Actions for Meadow Equine Referral and Rehabilitation Clinic\"]')"), await evaluate("document.body.innerText")
        await evaluate("document.querySelector('[aria-label=\"Actions for Meadow Equine Referral and Rehabilitation Clinic\"]').click()")
        await asyncio.sleep(.3)
        await click("View application")
        for width, height, mobile, name in [(1440, 900, False, "desktop"), (375, 812, True, "mobile"), (320, 700, True, "mobile-320")]:
            await command("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile})
            await asyncio.sleep(.3)
            metrics = await evaluate("""(() => {
                const d=document.querySelector('[role=dialog]');
                const panel=d.firstElementChild, footer=panel.querySelector('footer'), header=panel.querySelector('header');
                const body=[...panel.children].find(e=>getComputedStyle(e).overflowY==='auto');
                const rect=e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right,top:e.getBoundingClientRect().top,bottom:e.getBoundingClientRect().bottom});
                return {panel:rect(panel),footer:rect(footer),header:rect(header),bodyHeight:body.clientHeight,bodyScroll:body.scrollHeight,overflow:panel.scrollWidth>panel.clientWidth,buttons:[...footer.querySelectorAll('button')].map(b=>({text:b.innerText,overflow:b.scrollWidth>b.clientWidth,...rect(b)}))};
            })()""")
            assert metrics["panel"]["left"] >= 0 and metrics["panel"]["right"] <= width, metrics
            assert metrics["footer"]["bottom"] <= height and metrics["header"]["top"] >= 0, metrics
            assert not metrics["overflow"] and metrics["bodyScroll"] > metrics["bodyHeight"], metrics
            assert all(not b["overflow"] and b["bottom"] <= height and b["left"] >= 0 and b["right"] <= width for b in metrics["buttons"]), metrics
            print(name, json.dumps(metrics))
            screenshot = await command("Page.captureScreenshot", {"format": "png"})
            Path(f"screenshots/provider-application-{name}.png").write_bytes(base64.b64decode(screenshot["data"]))
        await click("Approve & stage listing")
        await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        await command("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        await asyncio.sleep(.3)
        assert await evaluate("document.querySelectorAll('[role=dialog]').length") == 1
        await click("Approve & stage listing")
        await click("Approve application")
        await asyncio.sleep(.5)
        assert await evaluate("document.querySelector('[role=dialog]').innerText.includes('Draft, unpublished')")
        assert await evaluate("document.querySelector('[role=dialog]').innerText.includes('Sports medicine and rehabilitation')")
        await click("Close")
        application.update(review_status="PENDING_REVIEW", provider_id=None, reviewed_at=None, reviewed_by_name=None)
        await command("Page.reload")
        await asyncio.sleep(3)
        await evaluate("document.querySelector('[aria-label=\"Actions for Meadow Equine Referral and Rehabilitation Clinic\"]').click()")
        await asyncio.sleep(.2)
        await click("View application")
        await click("Reject")
        await click("Reject application")
        await asyncio.sleep(.5)
        assert await evaluate("document.querySelector('[role=dialog]').innerText.includes('Browser rejection feedback')")
        assert await evaluate("document.querySelector('[role=dialog]').innerText.includes('Equine internal medicine')")
        print("Browser checks passed: scrolling, controls, Escape, and both decision refreshes.")
        reader.cancel()


asyncio.run(main())