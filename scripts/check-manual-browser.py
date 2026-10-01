"""Manual usability checks with synthetic authentication only; no live API traffic."""
import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets
from PIL import Image


async def main():
    origin = "https://" + os.environ["REPLIT_DEV_DOMAIN"]
    public_capture = "--capture-public" in sys.argv
    port = 9246 if public_capture else 9245
    with tempfile.TemporaryDirectory(prefix="manual-check-", ignore_cleanup_errors=True) as profile:
        browser = subprocess.Popen(
            ["chromium", "--headless", "--no-sandbox", "--disable-dev-shm-usage",
             f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        try:
            for _ in range(80):
                try:
                    targets = json.load(urlopen(f"http://127.0.0.1:{port}/json"))
                    target = next(t for t in targets if t["type"] == "page")
                    break
                except Exception:
                    await asyncio.sleep(.15)
            else:
                raise RuntimeError("Dedicated browser did not start")
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
                pending, errors = {}, []
                counter, role = 0, "anonymous" if public_capture else "admin"

                async def call(method, params=None):
                    nonlocal counter
                    counter += 1
                    future = asyncio.get_running_loop().create_future()
                    pending[counter] = future
                    await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                    response = await asyncio.wait_for(future, 20)
                    if "error" in response:
                        raise RuntimeError(response["error"])
                    return response.get("result", {})

                async def intercept(params):
                    path = urlparse(params["request"]["url"]).path
                    status = 200
                    if path.endswith("/auth/refresh"):
                        if role == "anonymous":
                            status, data = 401, {"detail": "Synthetic signed-out session"}
                        else:
                            data = {"access_token": "synthetic-browser-only", "user": {
                                "id": "sample-manual-user", "email": "sample.admin@example.test",
                                "full_name": "Sample Administrator", "first_name": "Sample",
                                "last_name": "Administrator", "role": role, "roles": [role],
                                "is_active": True, "email_verified_at": "2026-09-01T12:00:00Z",
                            }}
                    elif path.endswith("/system-settings"):
                        data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
                    elif path == "/api/v1/messages/unread":
                        data = {"count": 0}
                    elif public_capture and path == "/api/v1/public/providers":
                        data = []
                    elif public_capture and path in ["/api/v1/public/visits", "/api/v1/analytics/page-view"]:
                        data = {}
                    elif public_capture and path in ["/api/v1/public/contact", "/api/v1/public/subscribers"]:
                        data = {"message": "Sample submission accepted. No email was sent."}
                    else:
                        status, data = 501, {"detail": "No live API: unsupported manual fixture"}
                    await call("Fetch.fulfillRequest", {
                        "requestId": params["requestId"], "responseCode": status,
                        "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                        "body": base64.b64encode(json.dumps(data).encode()).decode(),
                    })

                async def receive():
                    async for raw in ws:
                        message = json.loads(raw)
                        if "id" in message:
                            future = pending.pop(message["id"], None)
                            if future:
                                future.set_result(message)
                        elif message.get("method") == "Fetch.requestPaused":
                            asyncio.create_task(intercept(message["params"]))
                        elif message.get("method") == "Runtime.exceptionThrown":
                            errors.append(message["params"]["exceptionDetails"])

                receiver = asyncio.create_task(receive())

                async def evaluate(expression):
                    result = await call("Runtime.evaluate", {
                        "expression": expression, "returnByValue": True, "awaitPromise": True,
                    })
                    if "exceptionDetails" in result:
                        raise AssertionError(result["exceptionDetails"])
                    return result["result"].get("value")

                async def wait(expression):
                    for _ in range(100):
                        if await evaluate(expression):
                            return
                        await asyncio.sleep(.12)
                    raise AssertionError({"body": await evaluate("document.body.innerText"), "errors": errors})

                async def click(expression):
                    assert await evaluate(f"(()=>{{ const e={expression}; if(!e)return false; e.click();return true; }})()"), expression
                    await asyncio.sleep(.2)

                async def screenshot(name, manual=False):
                    Path("screenshots").mkdir(exist_ok=True)
                    await evaluate("""(()=>{const b=document.createElement('div');b.id='manual-demo-label';
                      b.textContent='SAMPLE DATA — demonstration only';
                      b.style.cssText='position:fixed;bottom:8px;left:8px;z-index:99999;background:#173b30;color:white;padding:6px;font:12px sans-serif';document.body.append(b)})()""")
                    shot = await call("Page.captureScreenshot", {"format": "jpeg", "quality": 80})
                    raw = base64.b64decode(shot["data"])
                    if manual:
                        target_path = Path(f"frontend/public/manual/{name}.webp")
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        Image.open(BytesIO(raw)).save(target_path, "WEBP", quality=84, method=6)
                    else:
                        Path(f"screenshots/{name}.jpg").write_bytes(raw)
                    await evaluate("document.getElementById('manual-demo-label').remove()")

                await call("Page.enable")
                await call("Runtime.enable")
                await call("Fetch.enable", {"patterns": [{"urlPattern": origin + "/api/v1/*"}]})
                await call("Emulation.setDeviceMetricsOverride", {
                    "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
                })
                if public_capture:
                    await call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
                    await call("Page.navigate", {"url": origin + "/"})
                    await wait("!!document.querySelector('form[aria-label=\"Contact EquiConnected\"]')")
                    await asyncio.sleep(1)
                    await screenshot("public-find-care-start", manual=True)
                    await evaluate("""(()=>{
                        const f=document.querySelector('form[aria-label="Contact EquiConnected"]');
                        const set=(e,v)=>{Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}))};
                        set(f.querySelector('[name=name]'),'Sample Visitor');
                        set(f.querySelector('[name=email]'),'sample.visitor@example.test');
                        set(f.querySelector('[name=message]'),'Sample enquiry: please explain how to join the directory.');
                        f.scrollIntoView({block:'center',behavior:'instant'});
                    })()""")
                    await asyncio.sleep(.3)
                    await screenshot("public-contact-equiconnected", manual=True)
                    await click("document.querySelector('form[aria-label=\"Contact EquiConnected\"] button[type=submit]')")
                    await wait("document.body.innerText.includes('Thank you for reaching out.')")
                    await screenshot("public-contact-equiconnected-result", manual=True)
                    await evaluate("""(()=>{
                        const f=document.querySelector('form[aria-label="Get EquiConnected updates"]');
                        const s=f.querySelector('select');s.value=s.options[1].value;s.dispatchEvent(new Event('change',{bubbles:true}));
                        const e=f.querySelector('input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'sample.subscriber@example.test');e.dispatchEvent(new Event('input',{bubbles:true}));
                        f.scrollIntoView({block:'center',behavior:'instant'});
                    })()""")
                    await asyncio.sleep(.3)
                    await screenshot("public-subscribe-updates", manual=True)
                    await click("document.querySelector('form[aria-label=\"Get EquiConnected updates\"] button[type=submit]')")
                    await wait("!document.querySelector('form[aria-label=\"Get EquiConnected updates\"]')")
                    await screenshot("public-subscribe-updates-result", manual=True)
                    assert not errors, errors
                    print("Captured five public getting-started illustrations with synthetic submissions only.")
                    receiver.cancel()
                    return
                await call("Page.navigate", {"url": origin + "/admin/user-manual"})
                await wait("!!document.getElementById('manual-search')")
                assert await evaluate("document.querySelectorAll('main').length===1")
                await click("document.querySelector('[aria-label=\"Open profile menu\"]')")
                assert await evaluate("document.querySelector('[role=menu] [role=menuitem]').textContent.includes('User Manual')")
                assert await evaluate("document.querySelector('[href=\"/admin/user-manual\"]').getAttribute('aria-current')==='page'")
                await click("document.querySelector('[href=\"/admin/user-manual\"]')")
                assert await evaluate("!document.querySelector('[role=menu]')")
                await screenshot("manual-desktop")

                await evaluate("""(()=>{const e=document.getElementById('manual-search');
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'primary location');
                    e.dispatchEvent(new Event('input',{bubbles:true}))})()""")
                await wait("document.querySelectorAll('article').length>0 && document.querySelectorAll('article').length<30")
                await evaluate("""(()=>{const e=document.getElementById('manual-search');
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'no-such-manual-topic-999');
                    e.dispatchEvent(new Event('input',{bubbles:true}))})()""")
                await wait("document.body.innerText.includes('No matching topics')")
                assert await evaluate("document.querySelectorAll('[aria-label=\"Manual table of contents\"] a[href^=\"#\"]').length===0")
                await click("[...document.querySelectorAll('button')].find(e=>e.textContent.includes('Clear filters'))")
                await click("document.querySelector('[href=\"#section-dashboard-analytics\"]')")
                await wait("document.getElementById('section-dashboard-analytics')?.getBoundingClientRect().top<150")
                assert await evaluate("document.getElementById('section-dashboard-analytics').getBoundingClientRect().top>=60")
                await call("Page.reload")
                await wait("!!document.getElementById('manual-search')")
                await wait("document.getElementById('section-dashboard-analytics')?.getBoundingClientRect().top<150")

                await call("Emulation.setDeviceMetricsOverride", {
                    "width": 375, "height": 812, "screenWidth": 375, "screenHeight": 812,
                    "deviceScaleFactor": 1, "mobile": True,
                })
                await call("Page.navigate", {"url": origin + "/admin/user-manual"})
                await asyncio.sleep(.5)
                await wait("!!document.getElementById('manual-search')")
                await evaluate("window.scrollTo({top:0,behavior:'instant'})")
                await asyncio.sleep(.4)
                print("Mobile metrics:", await evaluate("({width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})"))
                print("Mobile overflow:", await evaluate("""[...document.querySelectorAll('body *')].filter(e=>{
                    const r=e.getBoundingClientRect();return r.right>380 && r.width>0
                }).slice(0,20).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,
                    right:e.getBoundingClientRect().right,text:e.textContent.slice(0,120)}))"""))
                print("Scroll content offenders:", await evaluate("""[...document.querySelectorAll('body *')].filter(e=>e.scrollWidth>e.clientWidth+10 && e.clientWidth>0).map(e=>({tag:e.tagName,cls:e.className,client:e.clientWidth,scroll:e.scrollWidth,text:e.textContent.slice(0,100)})).slice(0,25)"""))
                print("Viewport setup:", await evaluate("""({meta:document.querySelector('meta[name=viewport]')?.content,screen:screen.width,visual:visualViewport.width,
                    header:{left:getComputedStyle(document.querySelector('header')).left,right:getComputedStyle(document.querySelector('header')).right,width:getComputedStyle(document.querySelector('header')).width}})"""))
                await screenshot("manual-mobile")
                assert await evaluate("window.innerWidth===375")
                assert await evaluate("document.documentElement.scrollWidth<=window.innerWidth"), "Mobile horizontal overflow"
                image_button = "document.querySelector('button[aria-label^=\"Enlarge image:\"]')"
                await evaluate(f"{image_button}.scrollIntoView({{block:'center',behavior:'instant'}})")
                await click(image_button)
                await wait("!!document.querySelector('dialog[open] img')")
                assert await evaluate("document.querySelector('dialog img').naturalWidth>0")
                await click("[...document.querySelectorAll('dialog button')].find(e=>e.textContent.includes('Show full size'))")
                assert await evaluate("document.querySelector('dialog img').getBoundingClientRect().width>375")
                await screenshot("manual-mobile-enlarged")
                await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await wait("!document.querySelector('dialog[open]')")
                assert await evaluate("document.activeElement.getAttribute('aria-label')?.startsWith('Enlarge image:')")

                for role in ["anonymous", "horse_owner", "provider"]:
                    await call("Page.navigate", {"url": origin + "/admin/user-manual"})
                    await wait("!location.pathname.includes('/admin/user-manual')")
                    assert not await evaluate("!!document.getElementById('manual-search')")
                assert not errors, errors
                print("Passed: admin direct load/refresh, menu order/close/active, search/no-results, stable anchors, desktop, 375px emulation, real-size image, Escape focus, non-admin guards.")
                receiver.cancel()
        finally:
            try:
                os.killpg(browser.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            browser.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())