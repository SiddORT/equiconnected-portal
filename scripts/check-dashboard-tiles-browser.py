"""Check real OSM requests on the Replit page using browser-only admin fixtures.

Run Chromium with CDP on port 9222 first. No database writes, credentials,
tile interception, cache bypass, or bulk tile fetching.
"""
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets


async def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "fixed"
    origin = "https://" + os.environ["REPLIT_DEV_DOMAIN"]
    target = json.load(urlopen("http://127.0.0.1:9222/json"))[0]
    markers = [
        {"location_id": kind, "provider_id": kind, "provider_name": name,
         "provider_type": kind, "location_name": "Office", "address": "Fixture address",
         "city": "Austin", "latitude": 30.2672 + i * .001,
         "longitude": -97.7431 + i * .001, "is_primary": True}
        for i, (kind, name) in enumerate([
            ("HOSPITAL", "Browser Hospital"), ("CLINIC", "Browser Clinic"),
            ("DOCTOR", "Browser Doctor"),
        ])
    ]
    stats = {
        "active_providers": 3,
        "provider_counts": {"hospitals": 1, "clinics": 1, "doctors": 1},
        "invitation_counts": {"sent": 0, "accepted": 0, "rejected": 0},
        "registration_counts": {"registrations": 0, "verified": 0, "unverified": 0,
                                "horse_owners": 0, "stable_managers": 0},
        "visitor_visits": [], "location_markers": markers,
    }
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
        pending, requests, errors = {}, {}, []
        counter = 0

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
            path = urlparse(params["request"]["url"]).path
            if path == "/api/v1/auth/refresh":
                data = {"access_token": "browser-fixture", "user": {
                    "id": "browser-admin", "email": "admin@example.invalid",
                    "full_name": "Browser Admin", "role": "admin", "roles": ["admin"], "is_active": True,
                }}
            elif path == "/api/v1/admin/dashboard/stats":
                data = stats
            elif path == "/api/v1/admin/dashboard/visits":
                data = {"month": "2026-10", "today": "2026-10-01", "visits": []}
            elif path == "/api/v1/system-settings":
                data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
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
                    continue
                method, params = message.get("method"), message.get("params", {})
                if method == "Fetch.requestPaused":
                    asyncio.create_task(intercept(params))
                elif method == "Network.requestWillBeSent":
                    request = params["request"]
                    if urlparse(request["url"]).hostname == "tile.openstreetmap.org":
                        requests[params["requestId"]] = {
                            "url": request["url"], "headers": request["headers"],
                        }
                elif method == "Network.requestWillBeSentExtraInfo":
                    if params["requestId"] in requests:
                        requests[params["requestId"]]["headers"] = params["headers"]
                elif method == "Network.responseReceived" and params["requestId"] in requests:
                    response = params["response"]
                    requests[params["requestId"]].update(
                        status=response["status"], cached=response.get("fromDiskCache", False))
                elif method == "Network.loadingFailed" and params["requestId"] in requests:
                    requests[params["requestId"]]["error"] = params["errorText"]
                elif method == "Runtime.exceptionThrown":
                    errors.append(params["exceptionDetails"]["text"])

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result["result"].get("value")

        async def click(selector):
            assert await evaluate(f"""(() => {{
                const el=document.querySelector({json.dumps(selector)});
                if(!el)return false;
                el.dispatchEvent(new MouseEvent('click', {{bubbles:true}})); return true;
            }})()"""), selector
            await asyncio.sleep(.5)

        await command("Page.enable")
        await command("Runtime.enable")
        await command("Network.enable")
        await command("Fetch.enable", {"patterns": [{"urlPattern": origin + "/api/v1/*"}]})
        await command("Emulation.setDeviceMetricsOverride", {
            "width": 1280, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        await command("Page.navigate", {"url": origin + "/admin/dashboard?invitation_token=privacy-check&tab=map"})
        await asyncio.sleep(8)
        assert await evaluate("!!document.querySelector('.leaflet-container')"), await evaluate("document.body.innerText")
        await evaluate("document.querySelector('.leaflet-container').scrollIntoView({block:'center'})")
        await asyncio.sleep(1)
        assert await evaluate("document.querySelector('meta[name=referrer]').content") == "no-referrer"
        policies = await evaluate("[...document.querySelectorAll('.leaflet-tile')].map(i=>i.referrerPolicy)")
        if phase == "fixed":
            assert policies and set(policies) == {"strict-origin"}, policies
            assert requests
            for request in requests.values():
                referer = next((v for k, v in request["headers"].items() if k.lower() == "referer"), None)
                assert referer == origin + "/", request
                assert not any(k.lower() in ("pragma", "cache-control") for k in request["headers"])
            assert await evaluate("document.querySelectorAll('.leaflet-interactive').length") == 3
            await click(".leaflet-interactive")
            assert "Browser" in await evaluate("document.querySelector('.leaflet-popup').textContent")
            assert "Fixture address" in await evaluate("document.querySelector('.leaflet-popup').textContent")
            await click(".leaflet-popup-close-button")
            for kind, count in [("Hospital", 2), ("Clinic", 1), ("Doctor", 0)]:
                await click(f'button[aria-label="Hide {kind} locations"]')
                assert await evaluate("document.querySelectorAll('.leaflet-interactive').length") == count
            assert "No visible locations" in await evaluate("document.body.innerText")
            for kind in ("Hospital", "Clinic", "Doctor"):
                await click(f'button[aria-label="Show {kind} locations"]')
            before = await evaluate("document.querySelector('.leaflet-tile').src.split('/')[3]")
            await click(".leaflet-control-zoom-in")
            await asyncio.sleep(3)
            after = await evaluate("document.querySelector('.leaflet-tile').src.split('/')[3]")
            assert int(after) == int(before) + 1, (before, after)
            assert await evaluate("""[...document.querySelectorAll('.leaflet-tile')]
                .every(i=>i.complete && i.naturalWidth === 256)""")
            assert all(request.get("status") == 200 for request in requests.values()), requests
            assert await evaluate("document.querySelector('.leaflet-control-attribution a[href=\"https://www.openstreetmap.org/copyright\"]').textContent") == "OpenStreetMap"
        await evaluate("document.querySelector('.leaflet-container').scrollIntoView({block:'center'})")
        await asyncio.sleep(.5)
        image = await command("Page.captureScreenshot", {"format": "png"})
        Path("screenshots").mkdir(exist_ok=True)
        Path(f"screenshots/dashboard-tiles-{phase}.png").write_bytes(base64.b64decode(image["data"]))
        evidence = {"phase": phase, "fixture_data_only": True, "document_policy": "no-referrer",
                    "tile_policies": policies, "requests": list(requests.values()), "browser_errors": errors}
        Path(f"screenshots/dashboard-tiles-{phase}.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
        assert not errors, errors
        if phase == "fixed":
            stats["location_markers"] = []
            await command("Page.reload", {"ignoreCache": False})
            await asyncio.sleep(4)
            assert "No mappable locations" in await evaluate("document.body.innerText")
            assert not await evaluate("document.querySelector('.leaflet-container')")
            print("Filter, popup, zoom, attribution, both empty states, and query privacy checks passed.")
        reader.cancel()


asyncio.run(main())