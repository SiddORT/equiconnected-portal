"""Check the public About route at real responsive widths using Chromium CDP."""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import urlopen
import websockets


async def main():
    origin = "https://" + os.environ["REPLIT_DEV_DOMAIN"]
    with tempfile.TemporaryDirectory(prefix="about-browser-", ignore_cleanup_errors=True) as profile:
        browser = subprocess.Popen(
            ["chromium", "--headless", "--no-sandbox", "--disable-dev-shm-usage",
             "--remote-debugging-port=9258", f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                try:
                    target = next(t for t in json.load(urlopen("http://127.0.0.1:9258/json")) if t["type"] == "page")
                    break
                except Exception:
                    await asyncio.sleep(.1)
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=40_000_000) as ws:
                counter = 0

                async def call(method, params=None):
                    nonlocal counter
                    counter += 1
                    await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(await ws.recv())
                        if response.get("id") == counter:
                            if "error" in response:
                                raise RuntimeError(response["error"])
                            return response.get("result", {})

                async def evaluate(expression):
                    result = await call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
                    if "exceptionDetails" in result:
                        raise RuntimeError(result["exceptionDetails"])
                    return result["result"].get("value")

                await call("Page.enable")
                await call("Runtime.enable")
                Path("screenshots").mkdir(exist_ok=True)
                for width in (1440, 768, 375):
                    await call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width == 375,
                    })
                    await call("Page.navigate", {"url": origin + "/about"})
                    await asyncio.sleep(3)
                    await evaluate("document.fonts.ready")
                    await evaluate("""(async()=>{
                        for(let y=0;y<document.body.scrollHeight;y+=700){
                            window.scrollTo(0,y); await new Promise(r=>setTimeout(r,150));
                        }
                        await Promise.all(Array.from(document.images).map(i=>i.decode().catch(()=>{})));
                    })()""")
                    await asyncio.sleep(1)
                    await evaluate("window.scrollTo(0,0)")
                    checks = await evaluate("""({
                        path: location.pathname, title: document.title,
                        width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                        sections: Array.from(document.querySelectorAll('main > section')).map(s=>s.id),
                        brokenImages: Array.from(document.images).filter(i=>i.complete && !i.naturalWidth).map(i=>i.src),
                        overflow: Array.from(document.querySelectorAll('main h1,main h2,main h3,main p')).filter(e=>{
                            const r=e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth+1;
                        }).map(e=>e.textContent)
                    })""")
                    assert checks["path"] == "/about", checks
                    assert checks["title"] == "About EquiConnected | EquiConnected", checks
                    assert checks["scrollWidth"] <= width, checks
                    assert not checks["brokenImages"] and not checks["overflow"], checks
                    metrics = await call("Page.getLayoutMetrics")
                    size = metrics["cssContentSize"]
                    shot = await call("Page.captureScreenshot", {"format": "jpeg", "quality": 80,
                        "captureBeyondViewport": True,
                        "clip": {"x": 0, "y": 0, "width": width, "height": size["height"], "scale": 1}})
                    Path(f"screenshots/about-{width}.jpg").write_bytes(base64.b64decode(shot["data"]))
                    if width < 1100:
                        await evaluate("document.getElementById('about-menu-toggle').click()")
                        assert await evaluate("getComputedStyle(document.getElementById('about-navigation')).display") != "none"
                        await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
                        assert await evaluate("document.activeElement.id") == "about-menu-toggle"
                        assert await evaluate("getComputedStyle(document.getElementById('about-navigation')).display") == "none"
                    await call("Page.reload")
                    await asyncio.sleep(2)
                    assert await evaluate("location.pathname") == "/about"
                    print(json.dumps(checks))
                await evaluate("document.querySelector('a[href=\"/#how-it-works\"]').click()")
                await asyncio.sleep(3)
                assert await evaluate("location.pathname + location.hash") == "/#how-it-works"
                assert await evaluate("document.activeElement.id") == "steps-heading"
                await evaluate("document.querySelector('a[href=\"/about\"]').click()")
                await asyncio.sleep(2)
                assert await evaluate("location.pathname === '/about' && scrollY === 0")
                await evaluate("history.back()")
                await asyncio.sleep(2)
                assert await evaluate("location.pathname + location.hash") == "/#how-it-works"
                print("Direct load, refresh, responsive menus, homepage anchors and browser back passed.")
        finally:
            browser.terminate()
            browser.wait(timeout=10)


asyncio.run(main())