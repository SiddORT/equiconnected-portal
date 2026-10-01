"""Check trips against Locations using browser-only fixtures, never stored data.

Start Chromium with --remote-debugging-port=9222 before running this script.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets


async def main():
    target = next(t for t in json.load(urlopen("http://127.0.0.1:9222/json")) if t["type"] == "page")
    origin = "https://" + os.environ["REPLIT_DEV_DOMAIN"]
    address = "Long equine referral and rehabilitation campus, eastern paddock entrance, " + "A" * 160
    location = {"id": "location", "name": "North paddock", "address_line_1": address,
                "address_line_2": None, "city": "Calgary", "state_province": "Alberta",
                "country": "Canada", "postal_code": "T2P 1J9", "is_primary": True,
                "latitude": None, "longitude": None}
    provider = {
        "id": "browser-doctor", "provider_type": "DOCTOR", "name": "Browser doctor",
        "description": None, "website": None, "email": None, "phone": None,
        "visit_stability": "NOT_STABLE_VISIT", "status": "ACTIVE", "publication_status": "UNPUBLISHED",
        "doctor_availability": "VISITING", "locations": [location], "specializations": [],
        "languages": [], "photos": [], "phones": [], "emails": [], "qualifications": [],
        "thumbnail_url": None, "doctor_profile": None, "maximum_working_radius_km": None,
        "clinic_hospital_visit": False, "emergency_services_available": False,
        "doctor_visits": [
            {"id": period, "location": location, "start_date": start, "end_date": end}
            for period, start, end in [("past", "2000-01-01", "2000-01-02"),
                                      ("current", "2000-01-01", "2999-01-01"),
                                      ("future", "2999-06-01", "2999-06-03")]
        ],
    }
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
        pending, errors = {}, []
        counter = 0

        async def command(method, params=None):
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            response = await asyncio.wait_for(future, 20)
            assert "error" not in response, response
            return response.get("result", {})

        async def intercept(params):
            path = urlparse(params["request"]["url"]).path
            if path == "/api/v1/auth/refresh":
                data = {"access_token": "browser-fixture", "user": {
                    "id": "browser-admin", "email": "fixture@example.com", "full_name": "Browser admin",
                    "first_name": "Browser", "last_name": "Admin", "role": "admin", "roles": ["admin"],
                    "is_active": True, "email_verified_at": "2026-01-01T00:00:00Z"}}
            elif path == "/api/v1/system-settings":
                data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
            elif path == "/api/v1/admin/providers/browser-doctor":
                data = provider
            elif path == "/api/v1/admin/doctors/browser-doctor":
                data = {**provider, "organizations": []}
            elif path.endswith("/portal-access"):
                data = {"status": "eligible", "selectable_emails": [], "can_revoke": False}
            elif path == "/api/v1/admin/specializations":
                data = {"data": [], "meta": {"page": 1, "page_size": 100, "total": 0, "total_pages": 1}}
            else:
                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            await command("Fetch.fulfillRequest", {
                "requestId": params["requestId"], "responseCode": 200,
                "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                "body": base64.b64encode(json.dumps(data).encode()).decode()})

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    future = pending.pop(message["id"], None)
                    if future and not future.done():
                        future.set_result(message)
                elif message.get("method") == "Fetch.requestPaused":
                    asyncio.create_task(intercept(message["params"]))
                elif message.get("method") == "Runtime.exceptionThrown":
                    errors.append(message["params"])
                elif message.get("method") == "Runtime.consoleAPICalled" and message["params"]["type"] == "error":
                    errors.append(message["params"])

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            assert "exceptionDetails" not in result, result
            return result["result"].get("value")

        await command("Page.enable")
        await command("Runtime.enable")
        await command("Fetch.enable", {"patterns": [{"urlPattern": origin + "/api/v1/*"}]})
        await command("Page.navigate", {"url": origin + "/admin/providers/browser-doctor"})
        for _ in range(40):
            if await evaluate("document.body.innerText.includes('Doctor trips')"):
                break
            await asyncio.sleep(.25)
        else:
            raise AssertionError(await evaluate("document.body.innerText"))

        for width in [1440, 390, 320]:
            await command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": width < 500})
            await asyncio.sleep(.3)
            result = await evaluate("""(() => {
              const card = name => [...document.querySelectorAll('h2')].find(h => h.textContent === name).closest('[class*="card--pad"]');
              const trips = card('Doctor trips'), locations = card('Locations');
              const css = e => { const s = getComputedStyle(e); return [s.fontFamily, s.fontSize, s.fontWeight, s.color, s.lineHeight]; };
              const title = trips.querySelector('strong'), sub = title.nextElementSibling;
              const rect = e => { const r = e.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; };
              const contained = e => { const a=rect(e), b=rect(trips); return a.left>=b.left && a.right<=b.right && e.scrollWidth<=e.clientWidth; };
              const add = [...trips.querySelectorAll('button')].find(b=>b.textContent==='Add future return');
              const amend = [...trips.querySelectorAll('button')].find(b=>b.textContent==='Amend');
              const desc = trips.querySelector('p');
              return {width:innerWidth, title:css(title), locationTitle:css(locations.querySelector('[class*="itemTitle"]')),
                address:css(sub), locationSub:css(locations.querySelector('[class*="itemSub"]')), description:css(desc),
                wraps:contained(sub), actionsFit:contained(add)&&contained(amend),
                noOverlap:rect(add).left>=rect(desc).right || rect(add).top>=rect(desc).bottom,
                labels: [...trips.querySelectorAll('strong')].map(e=>e.textContent.split(' ·')[0])};
            })()""")
            print(json.dumps(result))
            assert result["width"] == width
            assert result["title"] == result["locationTitle"]
            assert result["address"] == result["locationSub"]
            assert result["description"][1] == "14px"
            assert result["wraps"] and result["actionsFit"] and result["noOverlap"]
            assert result["labels"] == ["Previous", "Current", "Upcoming"]
            await evaluate("""[...document.querySelectorAll('h2')].find(h=>h.textContent==='Doctor trips')
              .scrollIntoView({block:'start',behavior:'instant'})""")
            await asyncio.sleep(.2)
            shot = await command("Page.captureScreenshot", {"format": "png"})
            output = Path(f"/tmp/doctor-trips-{width}.png")
            output.write_bytes(base64.b64decode(shot["data"]))
        assert not errors, errors
        await command("Fetch.disable")
        reader.cancel()
        print("Browser checks passed: matching typography, wrapping and actions at 1440, 390 and 320px.")


asyncio.run(main())