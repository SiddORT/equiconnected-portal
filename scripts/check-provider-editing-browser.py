"""Synthetic owner-editing browser checks. Fail closed for all API requests.

Runs its own disposable Chromium session against the already-running dev app.
No real authentication, database writes, decisions or notifications are used.
"""
import asyncio
import base64
import copy
from datetime import date, timedelta
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image
import websockets

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated-artifacts/provider-editing"
REFERENCE = "/uploads/providers/browser-editing/photos/synthetic.png"


def profile():
    editable = dict(
        name="Synthetic provider editing fixture", first_name=None, last_name=None,
        doctor_availability=None, language_ids=["old"], description=None, website=None,
        email=None, phone=None, visit_stability="NOT_STABLE_VISIT",
        maximum_working_radius_km=None, emergency_services_available=False,
        emergency_contact_number=None, specialization_ids=[], locations=[], phones=[],
        emails=[], photos=[], qualifications=[], visit_additions=[],
        years_experience=0, biography=None, professional_title=None, experience_description=None,
    )
    return dict(
        id="browser-editing", name=editable["name"], description=None, email=None,
        phone=None, website=None, visit_stability="NOT_STABLE_VISIT",
        specializations=[], locations=[], photos=[], phones=[], emails=[],
        doctor_profile=None, doctor_fields_available=True, doctor_availability=None,
        can_schedule_visits=False, doctor_visits=[], qualifications=[], average_rating=None,
        review_count=0, visible_reviews=[], editable_profile=editable, profile_update=None,
        language_choices=[
            dict(id="en", name="English", code="en", is_active=True),
            dict(id="old", name="Retained synthetic language", code="old", is_active=False),
        ],
    )


async def check(ws_url, domain, png, file_path):
    stored = profile()
    patches, unexpected, errors, requests = [], [], [], []
    upload_count = 0
    broken = False
    async with websockets.connect(ws_url, max_size=15_000_000) as ws:
        pending, counter = {}, 0

        async def command(method, params=None):
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps(dict(id=counter, method=method, params=params or {})))
            result = await asyncio.wait_for(future, 25)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})

        async def intercept(params):
            nonlocal stored, upload_count
            request, request_id = params["request"], params["requestId"]
            path, method = urlparse(request["url"]).path, request["method"]
            if path.startswith("/api/"):
                requests.append(f"{method} {path}")
            # The Fetch pattern also matches Vite's /src/api/*.ts modules.
            # Only known local modules may pass; application API URLs never do.
            if not path.startswith(("/api/", "/uploads/")):
                parsed = urlparse(request["url"])
                if parsed.hostname == domain and path.startswith(("/src/", "/node_modules/")) and method == "GET":
                    await command("Fetch.continueRequest", dict(requestId=request_id))
                else:
                    unexpected.append(f"{method} {path}")
                    await command("Fetch.failRequest", dict(requestId=request_id, errorReason="BlockedByClient"))
                return
            status, content_type = 200, "application/json"
            if path.startswith("/uploads/"):
                status, content_type = (404 if broken else 200), "image/png"
                data = b"missing synthetic photo" if broken else png
            else:
                if path.endswith("/auth/refresh"):
                    body = dict(access_token="synthetic-browser-only", user=dict(
                        id="synthetic-owner", email="fixture@example.test",
                        full_name="Synthetic Provider", first_name="Synthetic", last_name="Provider",
                        role="provider", roles=["provider"], is_active=True,
                        email_verified_at="2026-01-01T00:00:00Z"))
                elif path.endswith("/system-settings"):
                    body = dict(timezone="UTC", date_format="month_day_year", time_format="12_hour")
                elif path.endswith("/messages/unread"):
                    body = dict(count=0)
                elif path.endswith("/provider/portal/specializations"):
                    body = []
                elif path.endswith("/provider/portal/profile/photos/upload") and method == "POST":
                    upload_count += 1
                    status = 201
                    body = dict(storage_reference=REFERENCE, alt_text="Synthetic clinic exterior",
                        caption="Synthetic image", display_order=0, is_thumbnail=False)
                elif path.endswith("/provider/portal/profile") and method == "GET":
                    body = copy.deepcopy(stored)
                elif path.endswith("/provider/portal/profile") and method == "PATCH":
                    patch = json.loads(request["postData"])
                    patches.append(copy.deepcopy(patch))
                    stored["editable_profile"].update(patch)
                    stored.update({key: copy.deepcopy(value) for key, value in patch.items()
                                   if key in stored and key != "editable_profile"})
                    stored["profile_update"] = None
                    for addition in patch.get("visit_additions", []):
                        stored["doctor_visits"].append(dict(
                            **addition, id=f"synthetic-trip-{len(stored['doctor_visits'])}"))
                    stored["editable_profile"]["visit_additions"] = []
                    body = copy.deepcopy(stored)
                else:
                    unexpected.append(f"{method} {path}")
                    await command("Fetch.failRequest", dict(requestId=request_id, errorReason="BlockedByClient"))
                    return
                data = json.dumps(body).encode()
            await command("Fetch.fulfillRequest", dict(requestId=request_id, responseCode=status,
                responseHeaders=[dict(name="Content-Type", value=content_type)],
                body=base64.b64encode(data).decode()))

        async def guarded_intercept(params):
            try:
                await intercept(params)
            except Exception as exc:
                errors.append(str(exc))
                await command("Fetch.failRequest", dict(requestId=params["requestId"], errorReason="BlockedByClient"))

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    future = pending.pop(message["id"], None)
                    if future and not future.done():
                        future.set_result(message)
                elif message.get("method") == "Fetch.requestPaused":
                    asyncio.create_task(guarded_intercept(message["params"]))
                elif message.get("method") == "Runtime.exceptionThrown":
                    errors.append(json.dumps(message["params"]["exceptionDetails"]))
                elif message.get("method") == "Runtime.consoleAPICalled" and message["params"]["type"] == "error":
                    errors.append(json.dumps(message["params"].get("args", [])))

        reader = asyncio.create_task(receive())
        async def evaluate(expression):
            result = await command("Runtime.evaluate", dict(expression=expression, returnByValue=True, awaitPromise=True))
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result["result"].get("value")

        async def wait(expression):
            for _ in range(150):
                if await evaluate(expression):
                    return
                await asyncio.sleep(.1)
            raise AssertionError(f"Timed out: {expression}\nRequests: {requests}\nUnexpected: {unexpected}\nErrors: {errors}\nURL: {await evaluate('location.href')}\n{await evaluate('document.body.innerText')}")

        async def click(text):
            assert await evaluate("""(() => {const e=[...document.querySelectorAll('button')]
                .find(e=>e.textContent.trim()===%s); if(!e)return false; e.click(); return true})()""" % json.dumps(text)), text
            await asyncio.sleep(.12)

        async def fill(label, value):
            assert await evaluate("""(() => {const l=[...document.querySelectorAll('label')]
                .find(e=>e.textContent.trim()===%s);const i=l?.control||l?.querySelector('input,textarea');
                if(!i)return false;Object.getOwnPropertyDescriptor(Object.getPrototypeOf(i),'value').set.call(i,%s);
                i.dispatchEvent(new Event('input',{bubbles:true})); i.dispatchEvent(new Event('change',{bubbles:true}));return true})()"""
                % (json.dumps(label), json.dumps(value))), label

        async def enter():
            await command("Input.dispatchKeyEvent", dict(type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, text="\r"))
            await command("Input.dispatchKeyEvent", dict(type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13))
            await asyncio.sleep(.1)

        async def capture(name):
            await evaluate("""(() => {
              const panel=document.querySelector('[role=tabpanel]:not([hidden])');
              const legends=[...document.querySelectorAll('legend')];
              let target=panel;
              if(%s.includes('classification')) target=legends.find(e=>e.textContent==='Doctor availability')?.parentElement;
              if(%s.includes('photo-error')) target=document.querySelector('[aria-label$="image failed to load"]');
              target?.scrollIntoView({block:'start'});
            })()""" % (json.dumps(name), json.dumps(name)))
            assert await evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"), "Horizontal overflow"
            shot = await command("Page.captureScreenshot", dict(format="png"))
            (OUTPUT / name).write_bytes(base64.b64decode(shot["data"]))

        try:
            await command("Page.enable")
            await command("Page.bringToFront")
            await command("Emulation.setFocusEmulationEnabled", dict(enabled=True))
            await command("Runtime.enable")
            await command("Network.enable")
            await command("Network.setCacheDisabled", dict(cacheDisabled=True))
            await command("Fetch.enable", dict(patterns=[
                dict(urlPattern="*/api/*"), dict(urlPattern="*/uploads/*"),
            ]))
            await command("Emulation.setDeviceMetricsOverride", dict(width=1440, height=1000, deviceScaleFactor=1, mobile=False))
            url = f"https://{domain}/provider/account"
            await command("Page.navigate", dict(url=url))
            await wait("!!document.querySelector('#portal-first-name')")
            await fill("First name", "Amina")
            await fill("Last name", "Rider")
            await evaluate("[...document.querySelectorAll('label')].find(e=>e.textContent.trim()==='English').querySelector('input').click()")
            await click("Save profile")
            await wait("document.body.innerText.includes('No further approval is needed')")
            assert patches[-1]["doctor_availability"] is None
            assert patches[-1]["language_ids"] == ["old", "en"]
            await capture("desktop-basic.png")
            await click("Services")
            assert await evaluate("![...document.querySelectorAll('[name=doctor-availability]')].some(e=>e.checked)")
            await evaluate("document.querySelector('[name=doctor-availability][value=VISITING]').focus()")
            await command("Input.dispatchKeyEvent", dict(type="keyDown", key=" ", code="Space", windowsVirtualKeyCode=32))
            await command("Input.dispatchKeyEvent", dict(type="keyUp", key=" ", code="Space", windowsVirtualKeyCode=32))
            await wait("!!document.querySelector('#provider-tab-visits')")
            await evaluate("document.querySelector('#provider-tab-visits').focus()")
            await enter()
            assert await evaluate("document.querySelector('#provider-tab-visits').getAttribute('aria-selected')==='true'")
            await click("Add visit")
            day = (date.today() + timedelta(days=20)).isoformat()
            await fill("Visit 1 start date", day)
            await fill("Visit 1 end date", day)
            await fill("Visit 1 address line 1", "42 Synthetic Visit Lane")
            await fill("Visit 1 city", "Dubai")
            await click("Services")
            assert await evaluate("document.querySelector('[value=ONGOING]').disabled")
            await click("Photos")
            root = await command("DOM.getDocument")
            node = await command("DOM.querySelector", dict(nodeId=root["root"]["nodeId"], selector="input[type=file]"))
            await command("DOM.setFileInputFiles", dict(nodeId=node["nodeId"], files=[str(file_path)]))
            await wait("!!document.querySelector('img[src^=\"blob:\"]')?.naturalWidth")
            await fill("Alt text", "Synthetic clinic exterior")
            await fill("Image title", "Synthetic image")
            await click("Upload photo")
            await wait("document.body.innerText.includes('Uploaded, not yet saved')")
            assert upload_count == 1
            await wait(f"!!document.querySelector('img[src=\"{REFERENCE}\"]')?.naturalWidth")
            assert not await evaluate("!!document.querySelector('img[src^=\"blob:\"]')")
            broken = True
            await evaluate(f"document.querySelector('img[src=\"{REFERENCE}\"]').src += '?synthetic-failure=1'")
            await wait("document.body.innerText.includes('Saving will not repair')")
            await capture("desktop-photo-error.png")
            broken = False
            await evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Retry image').focus()")
            assert await evaluate("document.activeElement.textContent==='Retry image'")
            await enter()
            await wait(f"!!document.querySelector('img[src=\"{REFERENCE}\"]')?.naturalWidth")
            await click("Save profile")
            await wait("document.body.innerText.includes('uploaded photos and profile changes have been saved')")
            assert patches[-1]["doctor_availability"] == "VISITING"
            assert patches[-1]["visit_additions"][0]["start_date"] == day
            assert patches[-1]["visit_additions"][0]["location"]["city"] == "Dubai"
            assert patches[-1]["first_name"] == "Amina" and patches[-1]["last_name"] == "Rider"
            await command("Page.navigate", dict(url=url + "?synthetic-reload=1"))
            await wait("document.querySelector('#portal-first-name')?.value==='Amina'")
            await click("Photos")
            await wait(f"!!document.querySelector('img[src=\"{REFERENCE}\"]')?.naturalWidth")
            assert not await evaluate("document.body.innerText.includes('Uploaded, not yet saved')")
            for width in (390, 360):
                await command("Emulation.setDeviceMetricsOverride", dict(width=width, height=900, deviceScaleFactor=1, mobile=True))
                await capture(f"mobile-{width}-photos.png")
                await click("Services")
                assert await evaluate("document.querySelector('[value=ONGOING]').disabled")
                await capture(f"mobile-{width}-classification.png")
                await click("Visits")
                assert not await evaluate("!!document.querySelector('[id$=\"-start-date\"]')")
                assert await evaluate("document.body.innerText.includes('Dubai')")
                await capture(f"mobile-{width}-visits.png")
                await click("Basic details")
                assert await evaluate("document.querySelector('#portal-last-name').value") == "Rider"
                await capture(f"mobile-{width}-names-languages.png")
                await click("Photos")
            assert not unexpected, unexpected
            assert not errors, errors
            print("PASS: synthetic desktop/mobile names, languages, unknown availability, keyboard Visiting selection, same-day independent visit, explicit photo staging/upload/save/reload, real browser image decoding, load failure and keyboard retry.")
            print(f"Captured labelled synthetic UI evidence in {OUTPUT.relative_to(ROOT)}")
        finally:
            reader.cancel()


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    domain = os.environ["REPLIT_DEV_DOMAIN"]
    image = BytesIO()
    Image.new("RGB", (80, 50), "#b7ac8e").save(image, "PNG")
    png = image.getvalue()
    with tempfile.TemporaryDirectory(prefix="provider-editing-browser-") as directory:
        file_path = Path(directory) / "synthetic-clinic.png"
        file_path.write_bytes(png)
        bundled = sorted(Path("/nix/store").glob("*playwright-chromium-cjk-*/chrome-linux/chrome"))
        executable = os.environ.get("CHROMIUM_BIN") or (str(bundled[0]) if bundled else "chromium")
        browser = subprocess.Popen([executable, "--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--remote-debugging-port=9231", f"--user-data-dir={directory}/chrome", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    targets = json.load(urlopen("http://127.0.0.1:9231/json", timeout=1))
                    target = next(item for item in targets if item["type"] == "page")
                    break
                except Exception:
                    await asyncio.sleep(.1)
            else:
                raise RuntimeError("Disposable Chromium did not start")
            await check(target["webSocketDebuggerUrl"], domain, png, file_path)
        finally:
            browser.terminate()
            browser.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
