"""Check real routed messaging with synthetic, fail-closed API fixtures only.

Run with the Frontend workflow active: python scripts/check-messages-theme-browser.py
No backend, credentials, persisted conversations or email delivery are used.
"""
import asyncio
import base64
import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import websockets

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("role_fixtures", ROOT / "scripts/capture-manual-role.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
OUT = ROOT / "screenshots/messages-theme"


async def run():
    fixtures = module.Fixtures()
    conversation_id = module.SAMPLE_MESSAGE_CONVERSATION_ID
    conversation = fixtures.message_conversations[conversation_id]
    conversation["conversation"]["provider_name"] = "Synthetic Meadow Equine Care " + "LongProviderName" * 10
    conversation["conversation"]["member_name"] = "Synthetic Member " + "LongMemberName" * 10
    module.SAMPLE_MESSAGE_CONTACT["name"] = conversation["conversation"]["member_name"]
    conversation["messages"][0]["body"] = "Synthetic layout check. " + "UnbrokenMessage" * 80
    domain = os.environ["REPLIT_DEV_DOMAIN"]
    origin = f"https://{domain}"
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="messages-theme-") as profile:
        chrome = subprocess.Popen(
            ["/repl/tools/bin/chromium", "--headless", "--no-sandbox", "--disable-dev-shm-usage",
             "--remote-debugging-port=9256", f"--user-data-dir={profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(80):
                try:
                    targets = json.load(urlopen("http://127.0.0.1:9256/json"))
                    target = next(t for t in targets if t["type"] == "page")
                    break
                except Exception:
                    await asyncio.sleep(.1)
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
                pending, tasks, failures = {}, [], []
                counter = 0

                async def command(method, params=None):
                    nonlocal counter
                    counter += 1
                    future = asyncio.get_running_loop().create_future()
                    pending[counter] = future
                    await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                    result = await asyncio.wait_for(future, 25)
                    if "error" in result:
                        raise RuntimeError(f"{method}: {result['error']}")
                    return result.get("result", {})

                async def route(params):
                    request = params["request"]
                    parsed = urlparse(request["url"])
                    try:
                        body = json.loads(request.get("postData") or "{}")
                        data, status = fixtures.reply(parsed.path, request["method"], parse_qs(parsed.query), body)
                        await command("Fetch.fulfillRequest", {
                            "requestId": params["requestId"], "responseCode": status,
                            "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                            "body": base64.b64encode(json.dumps(data).encode()).decode(),
                        })
                    except Exception as error:
                        if "Invalid InterceptionId" not in str(error):
                            failures.append(type(error).__name__)
                            await command("Fetch.failRequest", {"requestId": params["requestId"], "errorReason": "BlockedByClient"})

                async def receive():
                    async for raw in ws:
                        message = json.loads(raw)
                        if "id" in message:
                            future = pending.pop(message["id"], None)
                            if future and not future.done():
                                future.set_result(message)
                        elif message.get("method") == "Fetch.requestPaused":
                            tasks.append(asyncio.create_task(route(message["params"])))

                reader = asyncio.create_task(receive())

                async def evaluate(expression):
                    result = await command("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
                    assert "exceptionDetails" not in result, result
                    return result["result"].get("value")

                async def wait(expression):
                    for _ in range(120):
                        if await evaluate(expression):
                            return
                        await asyncio.sleep(.1)
                    raise AssertionError(f"Timeout: {expression}")

                async def capture(name):
                    await evaluate("""(() => {
                      let badge=document.getElementById('synthetic-evidence');
                      if(!badge){badge=document.createElement('div');badge.id='synthetic-evidence';
                        badge.textContent='SYNTHETIC FIXTURES · NO LIVE CONVERSATIONS';
                        badge.style.cssText='position:fixed;bottom:0;left:0;z-index:9999;background:#34362f;color:white;padding:3px 7px;font:10px sans-serif';
                        document.body.append(badge);}
                    })()""")
                    shot = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                    (OUT / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))

                async def click(selector):
                    await evaluate(f"document.querySelector({json.dumps(selector)}).click()")
                    await asyncio.sleep(.2)

                async def check(role, width, path, touch=None):
                    fixtures.role = role
                    await command("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 960, "deviceScaleFactor": 1, "mobile": width < 500,
                    })
                    await command("Emulation.setTouchEmulationEnabled", {"enabled": width < 500 if touch is None else touch})
                    await command("Page.navigate", {"url": origin + path})
                    await wait("!!document.querySelector('main h1') && !!document.querySelector('nav[aria-label]')")
                    if "?" in path:
                        await wait("!!document.querySelector('#first-private-message')")
                    elif path.endswith(conversation_id):
                        await wait("!!document.querySelector('#private-message-reply')")
                    else:
                        await wait("!!document.querySelector('aside li a')")
                    await asyncio.sleep(.4)
                    metrics = await evaluate("""(() => {
                      const h=document.querySelector('main h1'), nav=document.querySelector('header[role=banner]');
                      const body=document.querySelector('ol[aria-label="Conversation messages"] p');
                      const heading=document.querySelector('section h2');
                      return {banners:document.querySelectorAll('header[role=banner]').length,
                        navLabel:nav.querySelector('nav').getAttribute('aria-label'),
                        active:nav.querySelector('a[aria-current=page]')?.textContent,
                        navTop:nav.getBoundingClientRect().top,
                        overflow:document.documentElement.scrollWidth>innerWidth,
                        title:parseFloat(getComputedStyle(h).fontSize),
                        heading:heading?parseFloat(getComputedStyle(heading).fontSize):null,
                        body:body?parseFloat(getComputedStyle(body).fontSize):null};
                    })()""")
                    assert metrics["banners"] == 1 and metrics["navLabel"] == f"{role.title()} navigation", metrics
                    assert metrics["navTop"] >= 0 and "Messages" in metrics["active"], metrics
                    assert not metrics["overflow"] and 28 <= metrics["title"] <= 32, metrics
                    assert metrics["body"] is None or 13 <= metrics["body"] <= 14, metrics
                    if role == "member" and width < 500:
                        await click('button[aria-label="Open member navigation"]')
                        await capture(f"{role}-{width}-mobile-nav")
                        assert await evaluate("document.querySelector('nav[aria-label=\"Member navigation\"]').getBoundingClientRect().width <= innerWidth")
                        await click('button[aria-label="Close member navigation"]')
                        await click('button[aria-haspopup="menu"]')
                        assert await evaluate("document.querySelector('[role=menu]').getBoundingClientRect().left >= 0")
                        await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                        assert await evaluate("document.activeElement.matches('button[aria-haspopup=menu]')")
                    await capture(f"{role}-{width}-{'start' if '?' in path else 'thread' if path.endswith(conversation_id) else 'inbox'}")
                    print(role, width, path, metrics)
                    if path.endswith(conversation_id):
                        await evaluate("document.querySelector('button[type=submit]').scrollIntoView({block:'center',behavior:'instant'})")
                        await wait("document.querySelector('button[type=submit]').getBoundingClientRect().bottom <= innerHeight")
                        assert await evaluate("""(() => {
                          const reply=document.querySelector('#private-message-reply').getBoundingClientRect();
                          const send=document.querySelector('button[type=submit]').getBoundingClientRect();
                          return reply.top>=0 && reply.right<=innerWidth && send.top>=0 && send.right<=innerWidth;
                        })()""")
                        await capture(f"{role}-{width}-reply")
                        await click('a[href$="/messages"]')
                        await wait("!!document.querySelector('aside li a')")

                await command("Page.enable")
                await command("Runtime.enable")
                await command("Fetch.enable", {"patterns": [{"urlPattern": f"{origin}/api/*", "requestStage": "Request"}]})
                for role in ("member", "provider"):
                    for width in (1440, 768, 390, 360):
                        for path in (f"/{role}/messages", f"/{role}/messages/{conversation_id}"):
                            await check(role, width, path)
                        if role == "member":
                            await check(role, width, "/member/messages?provider_id=sample-clinic-id")
                fixtures.role = "member"
                await command("Page.navigate", {"url": origin + "/providers/sample-clinic-id"})
                await wait("!!document.querySelector('a[href=\"/member/messages?provider_id=sample-clinic-id\"]')")
                await click('a[href="/member/messages?provider_id=sample-clinic-id"]')
                await wait("!!document.querySelector('#first-private-message')")
                assert await evaluate("document.querySelectorAll('header[role=banner]').length===1")
                # Repeat a narrow member thread without touch emulation to cover
                # keyboard/desktop browsers at mobile-sized window widths.
                await check("member", 360, f"/member/messages/{conversation_id}", touch=False)
                assert not fixtures.unknown and not fixtures.fixture_failure and not failures, (fixtures.unknown, failures)
                reader.cancel()
                for task in tasks:
                    task.cancel()
                print("Messages theme browser checks passed. All API requests used synthetic fixtures.")
        finally:
            chrome.terminate()
            chrome.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(run())