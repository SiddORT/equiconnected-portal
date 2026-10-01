"""Check real routed messaging with synthetic, fail-closed API fixtures only.

Run: cd frontend && npm run test:messages-browser
Use --app-url http://127.0.0.1:5000 to check an already-running frontend.
No backend, credentials, persisted conversations or email delivery are used.
"""
import argparse
import asyncio
import base64
import importlib.util
import json
import os
import shutil
import signal
import socket
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


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_process(process):
    """Stop the entire disposable process group, including npm's Vite child."""
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except ProcessLookupError:
        process.wait()


async def wait_for_url(url, process):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError("Disposable process exited before becoming ready; see evidence logs.")
        try:
            with urlopen(url, timeout=.5) as response:
                return json.load(response) if url.endswith("/json") else None
        except (OSError, ValueError):
            await asyncio.sleep(.1)
    raise RuntimeError(f"Disposable process did not become ready: {url}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default=os.environ.get("MESSAGES_APP_URL"),
                        help="Existing frontend URL; otherwise start a disposable local Vite server.")
    parser.add_argument("--chromium", default=find_chromium())
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    if args.app_url:
        parsed = urlparse(args.app_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            parser.error("--app-url must be an HTTP(S) origin without credentials, path, query or fragment")
        args.app_url = args.app_url.rstrip("/")
    return args


def find_chromium():
    if os.environ.get("CHROMIUM_BIN"):
        return os.environ["CHROMIUM_BIN"]
    for name in ("google-chrome-stable", "google-chrome", "chromium"):
        executable = shutil.which(name)
        if executable and executable != "/repl/tools/bin/chromium":
            return executable
    # Replit also packages the stable browser used by its screenshot tooling.
    # Prefer that build: the rolling tools Chromium has crashed on long runs.
    bundled = sorted(Path("/nix/store").glob("*playwright-chromium-cjk-*/chrome-linux/chrome"))
    return str(bundled[0]) if bundled else "/repl/tools/bin/chromium"


async def run(args):
    task = asyncio.current_task()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
    fixtures = module.Fixtures()
    conversation_id = module.SAMPLE_MESSAGE_CONVERSATION_ID
    conversation = fixtures.message_conversations[conversation_id]
    conversation["conversation"]["provider_name"] = "Synthetic Meadow Equine Care " + "LongProviderName" * 10
    conversation["conversation"]["member_name"] = "Synthetic Member " + "LongMemberName" * 10
    module.SAMPLE_MESSAGE_CONTACT["name"] = conversation["conversation"]["member_name"]
    conversation["messages"][0]["body"] = "Synthetic layout check. " + "UnbrokenMessage" * 80
    origin = args.app_url
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    for old in [out / "failure.json", *out.glob("failure-*.png")]:
        old.unlink(missing_ok=True)
    frontend = None
    chrome = None
    safe_env = {key: value for key, value in os.environ.items()
                if key in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT")}
    frontend_log = (out / "frontend.log").open("w")
    chrome_log = (out / "chromium.log").open("w")
    with tempfile.TemporaryDirectory(prefix="messages-theme-") as profile:
        try:
            if not origin:
                port = free_port()
                origin = f"http://127.0.0.1:{port}"
                # A test-only config has NO backend proxy or application env files.
                # Do not inherit production credentials into the disposable server.
                config = ROOT / "frontend/vite.messages-check.config.ts"
                frontend = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--config", str(config),
                     "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
                    cwd=ROOT / "frontend", env=safe_env, start_new_session=True,
                    stdout=frontend_log, stderr=subprocess.STDOUT)
                await wait_for_url(origin, frontend)
            cdp_port = free_port()
            chrome = subprocess.Popen(
                [args.chromium, "--headless", "--no-sandbox", "--disable-dev-shm-usage",
                 "--disable-background-networking", "--no-first-run", "--disable-breakpad", "--disable-gpu",
                 f"--remote-debugging-port={cdp_port}", f"--user-data-dir={profile}", "about:blank"],
                env={**safe_env, "HOME": profile, "XDG_CONFIG_HOME": profile},
                start_new_session=True, stdout=chrome_log, stderr=subprocess.STDOUT)
            targets = await wait_for_url(f"http://127.0.0.1:{cdp_port}/json", chrome)
            target = next(t for t in targets if t["type"] == "page")
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
                pending, tasks, failures = {}, [], []
                counter = 0
                api_seen = []
                context = "startup"

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
                        is_api = parsed.path == "/api" or parsed.path.startswith("/api/")
                        # Vite loads JS modules using the Fetch resource type.
                        # Only known local static modules/assets may bypass fixtures.
                        local_static = request["url"].startswith(origin + "/") and (
                            parsed.path.startswith(("/src/", "/node_modules/", "/@"))
                            or Path(parsed.path).suffix in (".js", ".ts", ".tsx", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2")
                        )
                        is_data = params.get("resourceType") in ("XHR", "Fetch") and not local_static
                        if not is_api and not is_data:
                            if request["url"].startswith(origin + "/"):
                                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                                return
                            if params.get("resourceType") == "Stylesheet":
                                # No external font/network dependency in isolated CI.
                                await command("Fetch.fulfillRequest", {
                                    "requestId": params["requestId"], "responseCode": 200,
                                    "responseHeaders": [{"name": "Content-Type", "value": "text/css"}],
                                    "body": "",
                                })
                                return
                            raise AssertionError("Non-local static request blocked")
                        api_seen.append({"method": request["method"], "path": parsed.path})
                        body = json.loads(request.get("postData") or "{}")
                        data, status = fixtures.reply(parsed.path, request["method"], parse_qs(parsed.query), body)
                        if not status or status == 501:
                            raise AssertionError(f"Unmatched synthetic fixture: {request['method']} {parsed.path}")
                        await command("Fetch.fulfillRequest", {
                            "requestId": params["requestId"], "responseCode": status,
                            "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                            "body": base64.b64encode(json.dumps(data).encode()).decode(),
                        })
                    except Exception as error:
                        if "Invalid InterceptionId" not in str(error):
                            failures.append(f"{type(error).__name__}: {parsed.path}: {error}")
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
                    for _ in range(300):
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
                    (out / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))

                async def visible(selector):
                    # Viewport containment alone misses controls covered by overlays.
                    return await evaluate(f"""(() => {{
                      const el=document.querySelector({json.dumps(selector)});
                      if(!el) return false;
                      const r=el.getBoundingClientRect(), s=getComputedStyle(el);
                      if(r.width<=0 || r.height<=0 || r.left<0 || r.top<0 ||
                         r.right>innerWidth || r.bottom>innerHeight ||
                         s.visibility==='hidden' || s.display==='none') return false;
                      return [.2,.5,.8].every(x => [.2,.5,.8].every(y => {{
                        const top=document.elementFromPoint(r.left+r.width*x,r.top+r.height*y);
                        return top && (top===el || el.contains(top));
                      }}));
                    }})()""")

                async def click(selector):
                    await evaluate(f"document.querySelector({json.dumps(selector)}).click()")
                    await asyncio.sleep(.2)

                async def check(role, width, path, touch=None):
                    nonlocal context
                    context = f"{role}-{width}-{'start' if '?' in path else 'thread' if path.endswith(conversation_id) else 'inbox'}"
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
                        assert await visible('button[aria-label="Open member navigation"]'), "Obscured member menu toggle"
                    else:
                        assert await visible(f'nav[aria-label="{role.title()} navigation"] a[aria-current=page]'), "Obscured Messages navigation"
                    if role == "member" and width < 500:
                        await click('button[aria-label="Open member navigation"]')
                        assert await evaluate("document.querySelector('nav[aria-label=\"Member navigation\"]').getBoundingClientRect().width <= innerWidth")
                        assert await visible('nav[aria-label="Member navigation"] a[aria-current=page]'), "Obscured mobile Messages link"
                        assert await visible('button[aria-label="Close member navigation"]'), "Obscured menu close control"
                        await click('button[aria-label="Close member navigation"]')
                        await click('button[aria-haspopup="menu"]')
                        assert await evaluate("document.querySelector('[role=menu]').getBoundingClientRect().left >= 0")
                        await command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                        assert await evaluate("document.activeElement.matches('button[aria-haspopup=menu]')")
                    print(role, width, path, metrics)
                    if path.endswith(conversation_id) or "?" in path:
                        await evaluate("document.querySelector('button[type=submit]').scrollIntoView({block:'center',behavior:'instant'})")
                        await wait("document.querySelector('button[type=submit]').getBoundingClientRect().bottom <= innerHeight")
                        composer = "#first-private-message" if "?" in path else "#private-message-reply"
                        assert await visible(composer), "Obscured composer"
                        assert await visible('button[type=submit]'), "Obscured send control"
                        await click('a[href$="/messages"]')
                        await wait("!!document.querySelector('aside li a')")

                await command("Page.enable")
                await command("Runtime.enable")
                # Intercept ALL origins before navigating. Never continue API/data
                # requests, even if a future client switches to an absolute URL.
                await command("Network.setBypassServiceWorker", {"bypass": True})
                await command("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
                try:
                    await run_checks(check, command, wait, click, evaluate, fixtures, origin, conversation_id)
                    await asyncio.gather(*tasks)
                    assert api_seen, "No API fixtures were exercised"
                    assert not fixtures.unknown and not fixtures.fixture_failure and not failures, (fixtures.unknown, failures)
                    print("Messages theme browser checks passed. All API requests used synthetic fixtures.")
                except BaseException as error:
                    (out / "failure.json").write_text(json.dumps({
                        "provenance": "SYNTHETIC FIXTURES ONLY — NO LIVE CONVERSATIONS",
                        "case": context, "error": str(error) or type(error).__name__, "api_requests": api_seen,
                        "fixture_failures": failures, "unknown": fixtures.unknown,
                    }, indent=2))
                    try:
                        await capture("failure-" + context)
                    except Exception as capture_error:
                        print(f"Failure screenshot unavailable: {type(capture_error).__name__}")
                    raise
                finally:
                    reader.cancel()
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(reader, *tasks, return_exceptions=True)
        except BaseException as error:
            if not (out / "failure.json").exists():
                (out / "failure.json").write_text(json.dumps({
                    "provenance": "SYNTHETIC FIXTURES ONLY — NO LIVE CONVERSATIONS",
                    "case": "startup", "error": str(error) or type(error).__name__,
                }, indent=2))
            raise
        finally:
            try:
                stop_process(chrome)
            finally:
                try:
                    stop_process(frontend)
                finally:
                    frontend_log.close()
                    chrome_log.close()


async def run_checks(check, command, wait, click, evaluate, fixtures, origin, conversation_id):
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
    # Also cover a desktop/keyboard browser at a mobile-sized window width.
    await check("member", 360, f"/member/messages/{conversation_id}", touch=False)


if __name__ == "__main__":
    asyncio.run(run(parse_args()))