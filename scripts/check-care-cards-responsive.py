"""Responsive-only checks for the public homepage care cards.

Uses Chromium device emulation, including below its desktop window-size limit.
Run from the repository root. Screenshots are temporary, not project assets.
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
    with tempfile.TemporaryDirectory(prefix="care-responsive-", ignore_cleanup_errors=True) as profile:
        browser = subprocess.Popen(
            ["chromium", "--headless", "--no-sandbox", "--disable-dev-shm-usage",
             "--remote-debugging-port=9264", f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                try:
                    target = next(t for t in json.load(urlopen("http://127.0.0.1:9264/json"))
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
                for width in (375, 390, 768, 1440):
                    await call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 768,
                    })
                    await call("Page.navigate", {"url": origin + "/"})
                    for _ in range(100):
                        if await evaluate("!!document.getElementById('categories-heading')"):
                            break
                        await asyncio.sleep(.1)
                    await evaluate("""(async()=>{
                        await document.fonts.ready;
                        const section = document.querySelector('[aria-labelledby="categories-heading"]');
                        if (!section) throw new Error('Care section missing');
                        section.scrollIntoView({behavior:'instant', block:'start'});
                        await Promise.all([...section.querySelectorAll('img')].map(i=>i.decode()));
                    })()""")
                    await asyncio.sleep(.3)
                    result = await evaluate("""(()=>{
                        const s = document.querySelector('[aria-labelledby="categories-heading"]');
                        const cards = [...s.querySelectorAll('article')];
                        const descriptions = cards.map(c=>c.querySelector('p'));
                        const note = s.querySelector(':scope > div > p');
                        const rect = e => {
                            const r = e.getBoundingClientRect();
                            return {x:r.x, y:r.y, width:r.width, height:r.height, bottom:r.bottom};
                        };
                        const issues = [];
                        for (const el of [...descriptions, note]) {
                            if (!el) { issues.push('Missing text'); continue; }
                            const r = el.getBoundingClientRect(), css = getComputedStyle(el);
                            const range = document.createRange(); range.selectNodeContents(el);
                            if (css.display === 'none' || css.visibility !== 'visible' ||
                                Number(css.opacity) === 0 || r.height < 1) issues.push('Hidden text');
                            if (parseFloat(css.fontSize) < 12) issues.push('Text below 12px');
                            if (el.scrollWidth > el.clientWidth + 1 ||
                                el.scrollHeight > el.clientHeight + 1) issues.push('Clipped text');
                            for (const line of range.getClientRects()) {
                                if (line.left < r.left-1 || line.right > r.right+1 ||
                                    line.top < r.top-1 || line.bottom > r.bottom+1)
                                    issues.push('Text extends outside paragraph');
                            }
                        }
                        const overflow = [...s.querySelectorAll('*')].filter(e=>{
                            const r=e.getBoundingClientRect();
                            return r.left < -1 || r.right > innerWidth+1 ||
                                e.scrollWidth > e.clientWidth+1;
                        }).map(e=>e.tagName);
                        const gap = note.getBoundingClientRect().top -
                            Math.max(...cards.map(c=>c.getBoundingClientRect().bottom));
                        if (gap < 20) issues.push('Note too close to cards');
                        return {
                            width:innerWidth, visualWidth:visualViewport.width,
                            clientWidth:document.documentElement.clientWidth,
                            pageWidth:document.documentElement.scrollWidth,
                            columns:getComputedStyle(cards[0].parentElement).gridTemplateColumns,
                            cards:cards.map(rect), descriptions:descriptions.map(p=>p.textContent),
                            note:note.textContent, noteGap:gap, overflow, issues,
                            section:{top:s.getBoundingClientRect().top+scrollY,
                                     height:s.getBoundingClientRect().height}
                        };
                    })()""")
                    assert result["width"] == width, result
                    # Desktop scrollbars consume layout space within the emulated viewport.
                    assert abs(result["visualWidth"] - result["clientWidth"]) < 1, result
                    assert result["pageWidth"] == result["clientWidth"], result
                    assert not result["issues"] and not result["overflow"], result
                    cards = result["cards"]
                    if width < 768:
                        assert all(abs(c["x"] - cards[0]["x"]) < 1 for c in cards), result
                        assert all(cards[i]["y"] >= cards[i-1]["bottom"] + 20 for i in (1, 2)), result
                    else:
                        assert all(cards[i]["x"] > cards[i-1]["x"] + cards[i-1]["width"] for i in (1, 2)), result
                    shot = await call("Page.captureScreenshot", {
                        "format": "jpeg", "quality": 80, "captureBeyondViewport": True,
                        "clip": {"x": 0, "y": result["section"]["top"], "width": width,
                                 "height": result["section"]["height"], "scale": 1},
                    })
                    Path(f"/tmp/care-cards-{width}.jpg").write_bytes(base64.b64decode(shot["data"]))
                    print(json.dumps(result), flush=True)
        finally:
            browser.terminate()
            browser.wait(timeout=10)


asyncio.run(main())
