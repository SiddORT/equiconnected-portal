"""Check homepage photo/caption preservation at desktop and mobile widths.

Run after starting Frontend. Uses the existing Chromium/websockets harness
dependencies; screenshots go to a temporary directory, not Git.
"""
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
    with tempfile.TemporaryDirectory(prefix="home-photo-browser-") as profile:
        browser = subprocess.Popen(
            ["chromium", "--headless", "--no-sandbox", "--disable-dev-shm-usage",
             "--remote-debugging-port=9271", f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                try:
                    target = next(t for t in json.load(urlopen("http://127.0.0.1:9271/json"))
                                  if t["type"] == "page")
                    break
                except Exception:
                    await asyncio.sleep(.1)
            else:
                raise RuntimeError("Chromium did not expose a page")
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=40_000_000) as ws:
                counter = 0

                async def call(method, params=None):
                    nonlocal counter
                    counter += 1
                    await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(await asyncio.wait_for(ws.recv(), 30))
                        if response.get("id") == counter:
                            if "error" in response:
                                raise RuntimeError(response["error"])
                            return response.get("result", {})

                async def evaluate(expression):
                    result = await call("Runtime.evaluate", {
                        "expression": expression, "awaitPromise": True, "returnByValue": True,
                    })
                    if "exceptionDetails" in result:
                        raise RuntimeError(result["exceptionDetails"])
                    return result["result"].get("value")

                await call("Page.enable")
                await call("Emulation.setEmulatedMedia", {
                    "features": [{"name": "prefers-reduced-motion", "value": "reduce"}],
                })
                output = Path(tempfile.mkdtemp(prefix="home-photo-layout-"))
                for width in (1440, 390, 320):
                    await call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 768,
                    })
                    await call("Page.navigate", {"url": origin + "/"})
                    for _ in range(100):
                        if await evaluate("!!document.getElementById('contact-heading')"):
                            break
                        await asyncio.sleep(.1)
                    await evaluate("""(async()=>{
                        await document.fonts.ready;
                        for(const image of document.querySelectorAll('main img')) {
                            image.loading='eager';
                            await image.decode();
                        }
                    })()""")
                    checks = await evaluate("""(()=>{
                        const images=[...document.querySelectorAll('main img')];
                        const credits=[...document.querySelectorAll('main a[href*="unsplash.com"]')];
                        const text=document.querySelector('main').textContent;
                        const rect=e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height}};
                        const staleSelectors=['ownerCredits','photoCredit','categoryCredit','imageNote','whyCredit',
                            'visitingCredit','emergencyCredit','finalCredit'];
                        return {
                            imageCount:images.length,
                            broken:images.filter(i=>!i.naturalWidth).map(i=>i.src),
                            collapsed:images.filter(i=>{const r=rect(i);return r.width<1||r.height<1}).map(i=>i.src),
                            credits:credits.map(a=>a.textContent),
                            optionalCreditText:/Photo by|Hero photograph|Horse detail ·|Owner & horse ·|Philippe Oursel/i.test(text),
                            staleOverlays:staleSelectors.filter(c=>document.querySelector('[class*="'+c+'"]')),
                            emptyCaptions:[...document.querySelectorAll('figcaption')].filter(c=>!c.textContent.trim()).length,
                            providerCaption:document.querySelector('#providers figcaption')?.textContent,
                            contactForm:!!document.querySelector('#contact form[aria-label="Contact EquiConnected"]'),
                            overflow:document.documentElement.scrollWidth>innerWidth,
                            ownerImages:document.querySelectorAll('#owners img').length,
                            ownerAlt:document.querySelector('#owners img')?.alt,
                            ownerArch:getComputedStyle(document.querySelector('#owners img')).borderTopLeftRadius,
                            ownerDetailRound:getComputedStyle(document.querySelector('#owners img:nth-child(2)')).borderRadius,
                            ownerIllustration:!!document.querySelector('#owners [aria-label="Illustrative horse profile, not a member record"]'),
                            ownerSteps:document.querySelectorAll('#owners li').length,
                            ownerAction:document.querySelector('#owners a')?.getAttribute('href'),
                            ownerContentClipped:[...document.querySelectorAll('#owners img, #owners [aria-label], #owners h2, #owners li, #owners a')].some(e=>{
                                const r=e.getBoundingClientRect();return r.left<0||r.right>innerWidth||r.width<1||r.height<1;
                            })
                        };
                    })()""")
                    assert checks["imageCount"] == 15, checks
                    assert not checks["broken"] and not checks["collapsed"], checks
                    assert checks["credits"] == [], checks
                    assert not checks["optionalCreditText"] and not checks["staleOverlays"], checks
                    assert not checks["emptyCaptions"] and not checks["overflow"], checks
                    assert checks["providerCaption"] == "For the people behind equine care", checks
                    assert checks["contactForm"] and checks["ownerIllustration"], checks
                    assert checks["ownerImages"] == 2 and checks["ownerSteps"] == 6, checks
                    assert checks["ownerAlt"] == "A brown horse wearing a bridle, facing the camera", checks
                    assert checks["ownerArch"] == "999px" and checks["ownerDetailRound"] == "50%", checks
                    assert checks["ownerAction"] == "/signup" and not checks["ownerContentClipped"], checks
                    for section in ("providers", "owners", "emergency", "contact"):
                        await evaluate(f"document.getElementById('{section}').scrollIntoView({{block:'start',behavior:'instant'}})")
                        await asyncio.sleep(.15)
                        shot = await call("Page.captureScreenshot", {"format": "jpeg", "quality": 75})
                        (output / f"{section}-{width}.jpg").write_bytes(base64.b64decode(shot["data"]))
                    print(width, json.dumps(checks))
                print(f"Layout screenshots: {output}")
        finally:
            browser.terminate()
            browser.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
