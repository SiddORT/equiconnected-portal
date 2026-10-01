"""Synthetic CDP browser verification for provider engagement insights.

The page is exercised against intercepted API fixtures only. No request to an
``/api`` endpoint is ever allowed through to the running application, so this
check cannot read or mutate persisted application data.

The app should already be running in the existing workflow. Set
``REPLIT_DEV_DOMAIN`` to its browser-facing host and run:

    python3 scripts/check-provider-insights-browser.py

If no Chromium CDP endpoint is already available, this script starts a
temporary headless Chromium instance on port 9227.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import websockets


CDP_PORT = 9227
PROVIDER_NAME = "Willow Creek Equine"
SCREENSHOTS = Path("screenshots")
INSIGHTS_PATH = "/api/v1/provider/portal/insights"


def metric(
    value,
    *,
    status="full",
    note="",
    comparison_reason="Not enough history for a meaningful comparison.",
    from_date=None,
    change_percent=None,
    previous_value=None,
):
    return {
        "value": value,
        "definition": "Counted for the selected dates.",
        "coverage": {
            "status": status,
            "from": from_date,
            "note": note,
        },
        "comparison": {
            "change_percent": change_percent,
            "previous_value": previous_value,
            "reason": comparison_reason,
        },
    }


def insights_fixture(preset, date_from=None, date_to=None):
    today = datetime.now(timezone.utc).date()
    to_date = date_to or today.isoformat()
    if date_from:
        from_date = date_from
    elif preset == "last_7_days":
        from_date = (today - timedelta(days=6)).isoformat()
    elif preset == "this_month":
        from_date = today.replace(day=1).isoformat()
    else:
        from_date = (today - timedelta(days=29)).isoformat()

    if preset == "last_7_days":
        # Activity tracking was not yet available during this selection.
        unavailable = metric(
            None,
            status="unavailable",
            note="Tracking began after this period; activity is not available.",
            comparison_reason="No activity history is available for this period.",
            from_date=today.isoformat(),
        )
        return {
            "provider_name": PROVIDER_NAME,
            "timezone": "UTC",
            "today": today.isoformat(),
            "period": {
                "date_from": from_date,
                "date_to": to_date,
                "preset": preset,
            },
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "profile_views": unavailable,
                "contact_clicks": unavailable,
                "new_conversations": unavailable,
            },
            "contact_breakdown": {
                "phone": None,
                "email": None,
                "website": None,
            },
            "snapshot": {
                "saved_members": 8,
                "rating_count": 4,
                "visible_review_count": 3,
                "average_rating": 4.5,
            },
            "trends": [
                {"date": from_date, "profile_views": None, "contact_clicks": None},
                {"date": to_date, "profile_views": None, "contact_clicks": None},
            ],
        }

    if preset == "custom":
        profile_value = 44
        profile_metric = metric(profile_value)
    elif preset == "this_month":
        profile_value = 18
        profile_metric = metric(profile_value)
    else:
        profile_value = 24
        profile_metric = metric(
            profile_value,
            status="partial",
            note="Tracking began partway through this selection.",
            comparison_reason="partial_coverage",
            from_date=(today - timedelta(days=18)).isoformat(),
        )

    trend_start = profile_metric["coverage"]["from"] or from_date
    day_two = (datetime.fromisoformat(trend_start) + timedelta(days=1)).date().isoformat()
    fixture = {
        "provider_name": PROVIDER_NAME,
        "timezone": "UTC",
        "today": today.isoformat(),
        "period": {
            "date_from": from_date,
            "date_to": to_date,
            "preset": preset,
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "profile_views": profile_metric,
            "contact_clicks": metric(12),
            "new_conversations": metric(
                None,
                status="unknown",
                note="Conversation tracking is not yet confirmed for this period.",
                comparison_reason="coverage_unknown",
            ),
        },
        "contact_breakdown": {
            "phone": 5,
            "email": 4,
            "website": 3,
        },
        "snapshot": {
            "saved_members": 8,
            "rating_count": 4,
            "visible_review_count": 3,
            "average_rating": 4.5,
        },
        "trends": [
            {"date": trend_start, "profile_views": profile_value // 2, "contact_clicks": 3},
            {"date": day_two, "profile_views": profile_value - profile_value // 2, "contact_clicks": 9},
        ],
    }
    assert sum(fixture["contact_breakdown"].values()) == fixture["metrics"]["contact_clicks"]["value"]
    tracking_from = profile_metric["coverage"]["from"]
    if profile_metric["coverage"]["status"] == "partial" and tracking_from:
        assert all(point["date"] >= tracking_from for point in fixture["trends"])
    return fixture


class Browser:
    def __init__(self, websocket_url):
        self.websocket_url = websocket_url
        self.ws = None
        self.pending = {}
        self.counter = 0
        self.reader = None
        self.fetch_handler = None
        self.background_errors = []
        self.page_errors = []

    async def connect(self):
        self.ws = await websockets.connect(self.websocket_url, max_size=20_000_000)
        self.reader = asyncio.create_task(self._receive())

    async def close(self):
        if self.reader:
            self.reader.cancel()
        if self.ws:
            await self.ws.close()

    async def _receive(self):
        async for raw in self.ws:
            message = json.loads(raw)
            if "id" in message:
                future = self.pending.pop(message["id"], None)
                if future and not future.done():
                    future.set_result(message)
            elif message.get("method") == "Fetch.requestPaused" and self.fetch_handler:
                asyncio.create_task(self._handle_fetch(message["params"]))
            elif message.get("method") == "Runtime.exceptionThrown":
                self.page_errors.append(message["params"].get("exceptionDetails", {}))
            elif message.get("method") == "Log.entryAdded":
                entry = message["params"].get("entry", {})
                if entry.get("level") == "error":
                    self.page_errors.append({"source": "console", "text": entry.get("text", "")})

    async def _handle_fetch(self, params):
        try:
            await self.fetch_handler(params)
        except Exception as error:
            # Chrome may report a canceled Fetch request when React StrictMode
            # aborts its first development-only request. Keep other failures
            # visible to the check and never continue the request to the app.
            self.background_errors.append(str(error))

    async def call(self, method, params=None):
        self.counter += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.counter] = future
        await self.ws.send(json.dumps({
            "id": self.counter,
            "method": method,
            "params": params or {},
        }))
        result = await asyncio.wait_for(future, timeout=20)
        if "error" in result:
            raise RuntimeError(f"{method}: {result['error']}")
        return result.get("result", {})

    async def evaluate(self, expression):
        result = await self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if "exceptionDetails" in result:
            raise RuntimeError(f"Browser evaluation failed: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    async def wait_for(self, expression, description, timeout=15):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if await self.evaluate(expression):
                return
            await asyncio.sleep(0.15)
        diagnostic = await self.evaluate("""(() => ({
            url: location.href,
            title: document.title,
            readyState: document.readyState,
            bodyText: document.body?.innerText || document.documentElement?.innerText || '',
            bodyHtml: document.body?.innerHTML?.slice(0, 2400) || ''
        }))()""")
        raise AssertionError(
            f"Timed out waiting for {description}.\n"
            f"Browser state: {json.dumps(diagnostic, ensure_ascii=False)}\n"
            f"Page errors: {json.dumps(self.page_errors, ensure_ascii=False)}"
        )

    async def click_text(self, text):
        clicked = await self.evaluate(
            "(() => { const target = [...document.querySelectorAll('button,a')].find("
            f"element => element.innerText.trim() === {json.dumps(text)}); "
            "if (!target) return false; target.click(); return true; })()"
        )
        assert clicked, f"Could not find clickable text {text!r}."
        await asyncio.sleep(0.15)

    async def set_value(self, selector, value):
        expression = (
            "(() => { const input = document.querySelector("
            f"{json.dumps(selector)}); if (!input) return false; "
            "const type = input instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement; "
            "const setter = Object.getOwnPropertyDescriptor(type.prototype, 'value').set; "
            f"setter.call(input, {json.dumps(value)}); "
            "input.dispatchEvent(new Event('input', { bubbles: true })); "
            "input.dispatchEvent(new Event('change', { bubbles: true })); return true; })()"
        )
        assert await self.evaluate(expression), f"Could not set {selector} to {value!r}."
        await asyncio.sleep(0.15)

    async def open_trend_tables(self):
        opened = await self.evaluate("""(() => {
            const summaries = [...document.querySelectorAll('section[aria-label="Engagement trends"] details summary')]
                .filter((summary) => summary.innerText.trim() === 'View data table');
            summaries.forEach((summary) => summary.click());
            return summaries.length;
        })()""")
        assert opened == 2, f"Expected two trend data-table controls, found {opened}."
        await self.wait_for(
            "document.querySelectorAll('section[aria-label=\"Engagement trends\"] table').length === 2",
            "the accessible trend data tables",
        )

    async def viewport(self, width, height, mobile, screenshot):
        await self.call("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": mobile,
        })
        await asyncio.sleep(0.3)
        dimensions = await self.evaluate("""(() => ({
            innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            bodyWidth: document.body.scrollWidth,
            innerHeight
        }))()""")
        assert dimensions["documentWidth"] <= width and dimensions["bodyWidth"] <= width, (
            f"Horizontal overflow at {width}px: {dimensions}"
        )
        result = await self.call("Page.captureScreenshot", {
            "format": "jpeg",
            "quality": 88,
            "fromSurface": True,
        })
        SCREENSHOTS.mkdir(exist_ok=True)
        path = SCREENSHOTS / screenshot
        path.write_bytes(base64.b64decode(result["data"]))
        print(f"PASS viewport {width}x{height}; captured {path}")
        return dimensions


def browser_targets():
    try:
        with urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=1) as response:
            return json.load(response)
    except Exception:
        return None


def chromium_binary():
    return next(
        (
            shutil.which(candidate)
            for candidate in (
                "chromium",
                "chromium-browser",
                "google-chrome",
                "google-chrome-stable",
                "chrome",
            )
            if shutil.which(candidate)
        ),
        None,
    )


async def main():
    domain = os.environ.get("REPLIT_DEV_DOMAIN")
    if not domain:
        raise RuntimeError("Set REPLIT_DEV_DOMAIN to the already-running app host.")
    app_url = f"https://{domain}".rstrip("/")
    targets = browser_targets()
    launched_process = None
    profile_dir = None
    if not targets:
        binary = chromium_binary()
        if not binary:
            raise RuntimeError("No CDP browser is listening on port 9227 and Chromium was not found.")
        profile_dir = tempfile.mkdtemp(prefix="provider-insights-cdp-")
        launched_process = subprocess.Popen(
            [
                binary,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={CDP_PORT}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile_dir}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            targets = browser_targets()
            if targets:
                break
            if launched_process.poll() is not None:
                raise RuntimeError("The temporary Chromium process exited before CDP became ready.")
            await asyncio.sleep(0.1)
        if not targets:
            raise RuntimeError(f"Chromium did not open its CDP endpoint on port {CDP_PORT}.")

    page_target = next((item for item in targets if item.get("type") == "page"), None)
    if not page_target:
        raise RuntimeError(f"No page target is available on CDP port {CDP_PORT}.")

    state = {
        "requests": [],
        "initial_delay": True,
        "month_request_count": 0,
        "month_retry_allowed": False,
        "unexpected_api_requests": [],
        "expire_session": False,
    }
    browser = Browser(page_target["webSocketDebuggerUrl"])
    assertions = []
    await browser.connect()

    async def fulfill(request_id, body, status=200):
        encoded = base64.b64encode(json.dumps(body, separators=(",", ":")).encode()).decode()
        await browser.call("Fetch.fulfillRequest", {
            "requestId": request_id,
            "responseCode": status,
            "responseHeaders": [
                {"name": "Content-Type", "value": "application/json; charset=utf-8"},
                {"name": "Cache-Control", "value": "no-store"},
            ],
            "body": encoded,
        })

    async def intercept(params):
        request = params["request"]
        parsed = urlparse(request["url"])
        path = parsed.path
        method = request.get("method", "GET").upper()
        query = parse_qs(parsed.query)
        state["requests"].append({"method": method, "path": path, "query": parsed.query})

        # The exact origin plus the API root avoids intercepting source modules
        # such as /src/api/client.ts while still catching every app API route.
        status = 200
        body = {"detail": {"message": "Unmocked endpoint intercepted by the synthetic browser check."}}
        known_path = (
            path.endswith("/auth/refresh")
            or path == "/api/v1/system-settings"
            or path == "/api/v1/messages/unread"
            or path == "/api/v1/messages/inbox"
            or path == INSIGHTS_PATH
        )
        if not known_path:
            state["unexpected_api_requests"].append({"method": method, "path": path})

        if path.endswith("/auth/refresh"):
            if state["expire_session"]:
                status = 401
                body = {"detail": {"code": "session_expired", "message": "Session expired."}}
            else:
                body = {
                    "access_token": "synthetic-provider-insights-token",
                    "token_type": "bearer",
                    "expires_in": 900,
                    "user": {
                        "id": "browser-provider",
                        "email": "insights-owner@example.test",
                        "first_name": "Browser",
                        "last_name": "Provider",
                        "full_name": "Browser Provider",
                        "role": "provider",
                        "roles": ["provider"],
                        "is_active": True,
                        "email_verified_at": "2026-10-01T00:00:00Z",
                    },
                }
        elif path == "/api/v1/system-settings":
            body = {
                "timezone": "UTC",
                "date_format": "month_day_year",
                "time_format": "12_hour",
            }
        elif path == "/api/v1/messages/unread":
            body = {"count": 0}
        elif path == "/api/v1/messages/inbox":
            body = {"items": [], "page": 1, "page_size": 20, "total": 0}
        elif path == INSIGHTS_PATH and method == "GET":
            preset = query.get("preset", ["last_30_days"])[0]
            date_from = query.get("date_from", [None])[0]
            date_to = query.get("date_to", [None])[0]
            if state["initial_delay"] and preset == "last_30_days":
                # Leave the initial API call pending long enough to assert that
                # the page exposes its loading state, including in StrictMode.
                await asyncio.sleep(1.1)
                state["initial_delay"] = False
            if preset == "this_month":
                state["month_request_count"] += 1
                if not state["month_retry_allowed"]:
                    status = 503
                    body = {"detail": {"message": "Synthetic upstream failure for retry verification."}}
                elif state["expire_session"]:
                    status = 401
                    body = {"detail": {"code": "session_expired", "message": "Session expired."}}
                else:
                    body = insights_fixture(preset, date_from, date_to)
            elif state["expire_session"]:
                status = 401
                body = {"detail": {"code": "session_expired", "message": "Session expired."}}
            else:
                body = insights_fixture(preset, date_from, date_to)

        await fulfill(params["requestId"], body, status)

    browser.fetch_handler = intercept
    report = {
        "route": "/provider/insights",
        "origin": app_url,
        "screenshots": [],
        "assertions": assertions,
    }

    try:
        await browser.call("Page.enable")
        await browser.call("Runtime.enable")
        await browser.call("Log.enable")
        await browser.call("Fetch.enable", {
            "patterns": [{"urlPattern": f"{app_url}/api/*", "requestStage": "Request"}],
        })
        await browser.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 960,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        await browser.call("Page.navigate", {"url": f"{app_url}/provider/insights"})

        # Loading is checked while the initial synthetic insight request is
        # pending; the page then must settle into current data without a stale
        # StrictMode response replacing the winning response.
        await browser.wait_for(
            "(document.body?.innerText || '').includes('Loading your engagement')",
            "the insights loading state",
        )
        assert any(item["path"] == INSIGHTS_PATH for item in state["requests"]), (
            "No insights API request was intercepted during loading."
        )
        assertions.append("initial loading state rendered while the intercepted request was pending")

        await browser.wait_for(
            f"document.querySelector('h1')?.innerText.includes({json.dumps(PROVIDER_NAME)})",
            "the initial insights response",
        )
        await browser.wait_for(
            "document.querySelectorAll('section[aria-label=\"Engagement metrics\"] article').length === 3",
            "three engagement metric cards",
        )

        initial_metrics = await browser.evaluate("""(() => ({
            cards: [...document.querySelectorAll('section[aria-label="Engagement metrics"] article')].map((item) => item.innerText),
            trendTitles: [...document.querySelectorAll('section[aria-label="Engagement trends"] h3')].map((item) => item.innerText.trim()),
            trendCharts: [...document.querySelectorAll('section[aria-label="Engagement trends"] [role="img"]')].map((item) => item.getAttribute('aria-label')),
            snapshot: document.querySelector('section[aria-label="Current snapshot"]')?.innerText,
            snapshotHeading: [...document.querySelectorAll('h2')].some((item) => item.innerText.trim() === 'Current snapshot'),
            messageHref: document.querySelector('nav[aria-label="Provider navigation"] a[href="/provider/messages"]')?.getAttribute('href')
        }))()""")
        assert any("24*" in card for card in initial_metrics["cards"]), initial_metrics["cards"]
        assert any("Partial coverage" in card for card in initial_metrics["cards"]), initial_metrics["cards"]
        assert all("%" not in card for card in initial_metrics["cards"]), (
            "A percentage comparison was shown despite partial coverage."
        )
        assert any(
            "A comparison isn’t shown because this period is only partly covered." in card
            for card in initial_metrics["cards"]
        ), initial_metrics["cards"]
        assert all(
            raw_code not in card
            for card in initial_metrics["cards"]
            for raw_code in ("partial_coverage", "coverage_unknown")
        ), initial_metrics["cards"]
        assert any("Not available" in card for card in initial_metrics["cards"]), initial_metrics["cards"]
        assert initial_metrics["trendTitles"] == ["Profile visits", "Contact clicks"], initial_metrics["trendTitles"]
        assert len(initial_metrics["trendCharts"]) == 2, initial_metrics["trendCharts"]
        assert all(any(title in (label or "") for title in initial_metrics["trendTitles"])
                   for label in initial_metrics["trendCharts"]), initial_metrics["trendCharts"]
        assert initial_metrics["snapshotHeading"] and "Members who saved you" in initial_metrics["snapshot"], initial_metrics
        assert initial_metrics["messageHref"] == "/provider/messages", initial_metrics["messageHref"]
        assertions.extend([
            "provider metrics render as accessible cards, with coverage-aware unavailable values",
            "trends expose labelled data tables with captions and column headers",
            "partial coverage is labelled and suppresses percentage comparisons",
            "backend comparison reason codes are replaced with plain-English explanations",
            "provider navigation retains the Messages route",
        ])
        print("PASS initial cards, trends, accessible tables, partial coverage, and Messages navigation")

        # Capture baseline screenshots at the requested desktop and mobile sizes.
        for width, height, mobile, filename in (
            (1440, 960, False, "provider-insights-desktop.jpg"),
            (360, 800, True, "provider-insights-mobile360.jpg"),
            (390, 844, True, "provider-insights-mobile390.jpg"),
        ):
            await browser.viewport(width, height, mobile, filename)
            report["screenshots"].append(str(SCREENSHOTS / filename))
        await browser.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 960,
            "deviceScaleFactor": 1,
            "mobile": False,
        })

        await browser.click_text("Messages")
        await browser.wait_for(
            "location.pathname === '/provider/messages'",
            "the provider Messages route",
        )
        await browser.wait_for(
            "document.querySelector('main') && document.body.innerText.includes('Messages')",
            "the provider Messages page",
        )
        assertions.append("the existing provider Messages navigation still reaches its route")
        await browser.call("Page.navigate", {"url": f"{app_url}/provider/insights"})
        await browser.wait_for(
            f"document.querySelector('h1')?.innerText.includes({json.dumps(PROVIDER_NAME)})",
            "return navigation to provider insights",
        )
        await browser.wait_for(
            "document.querySelectorAll('section[aria-label=\"Engagement metrics\"] article').length === 3",
            "insights data after returning from Messages",
        )

        await browser.open_trend_tables()
        tables = await browser.evaluate("""[...document.querySelectorAll('section[aria-label="Engagement trends"] table')].map((table) => ({
            caption: table.caption?.textContent.trim(),
            headers: [...table.querySelectorAll('thead th')].map((header) => header.innerText.trim())
        }))""")
        assert len(tables) == 2 and all(table["caption"] and table["headers"] for table in tables), tables
        assertions.append("trend data tables expose accessible captions and column headers")

        snapshot_before = initial_metrics["snapshot"]
        await browser.set_value("#insights-period", "custom")
        await browser.wait_for("!!document.querySelector('#insights-from') && !!document.querySelector('#insights-to')",
                              "custom date inputs")
        custom_from = (datetime.now(timezone.utc).date() - timedelta(days=20)).isoformat()
        custom_to = (datetime.now(timezone.utc).date() - timedelta(days=15)).isoformat()
        await browser.set_value("#insights-from", custom_from)
        await browser.set_value("#insights-to", custom_to)
        await browser.click_text("Apply dates")
        await browser.wait_for(
            "document.querySelector('section[aria-label=\"Engagement metrics\"] article')?.innerText.includes('44')",
            "custom-date response",
        )
        custom_requests = [
            item for item in state["requests"]
            if item["path"] == INSIGHTS_PATH and "preset=custom" in item["query"]
        ]
        assert custom_requests, state["requests"]
        params = parse_qs(custom_requests[-1]["query"])
        assert params.get("date_from") == [custom_from] and params.get("date_to") == [custom_to], params
        custom_details = await browser.evaluate("""(() => ({
            snapshot: document.querySelector('section[aria-label="Current snapshot"]')?.innerText,
            period: [...document.querySelectorAll('h2')].find((node) => node.innerText.trim() === 'Activity in this period')?.parentElement?.innerText || ''
        }))()""")
        assert custom_details["snapshot"] == snapshot_before, (
            f"Date selection changed the live snapshot: {custom_details['snapshot']!r}"
        )
        from_label = datetime.fromisoformat(custom_from).strftime("%b %-d")
        to_label = datetime.fromisoformat(custom_to).strftime("%b %-d")
        assert from_label in custom_details["period"] and to_label in custom_details["period"], (
            "The selected custom dates were not reflected in the displayed period: "
            f"{custom_details['period']!r}"
        )
        assertions.append("custom dates are submitted and the current snapshot remains period-independent")
        print("PASS custom date request and date-independent current snapshot")

        # Before tracking began, nulls must remain explicitly unavailable in
        # cards and trend data rather than being misrepresented as zero.
        await browser.set_value("#insights-period", "last_7_days")
        await browser.click_text("Apply dates")
        await browser.wait_for(
            "document.querySelector('section[aria-label=\"Engagement metrics\"]')?.innerText.includes('Unavailable')",
            "pre-tracking unavailable coverage",
        )
        await asyncio.sleep(0.2)
        unavailable = await browser.evaluate("""(() => ({
            cards: [...document.querySelectorAll('section[aria-label="Engagement metrics"] article')].map((item) => item.innerText),
            trendTitles: [...document.querySelectorAll('section[aria-label="Engagement trends"] h3')].map((item) => item.innerText.trim()),
            trendTables: [...document.querySelectorAll('section[aria-label="Engagement trends"] table tbody')].map((tbody) => tbody.innerText)
        }))()""")
        assert all("Not available" in card for card in unavailable["cards"]), unavailable["cards"]
        assert unavailable["trendTitles"] == ["Profile visits", "Contact clicks"], unavailable["trendTitles"]
        assert all("Unavailable" in table and not any(row.strip().endswith(" 0") for row in table.splitlines())
                   for table in unavailable["trendTables"]), unavailable["trendTables"]
        assertions.append("pre-tracking nulls remain unavailable instead of being shown as invented zeros")
        print("PASS pre-tracking unavailable values and null trend rows")

        # A failure remains visible and does not silently reissue until the
        # user explicitly retries. The first this-month request fails; retry
        # receives a distinct successful fixture.
        await browser.set_value("#insights-period", "this_month")
        await browser.click_text("Apply dates")
        await browser.wait_for(
            "document.querySelector('[role=\"alert\"]')?.innerText.includes('load your insights just now')",
            "an explicit retryable insights error",
        )
        month_count_at_error = state["month_request_count"]
        assert month_count_at_error > 0, month_count_at_error
        await asyncio.sleep(1.0)
        assert state["month_request_count"] == month_count_at_error, (
            "The failed request was retried without user action."
        )
        assert await browser.evaluate("!![...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Try again')"), (
            "The explicit error state did not expose its retry control."
        )
        assertions.append("retryable failures remain visible until the user explicitly retries")
        print("PASS explicit, stable retryable error state")

        # The synthetic response stays failed until this explicit user retry;
        # only then does the handler allow the recovery response.
        state["month_retry_allowed"] = True
        await browser.click_text("Try again")
        await browser.wait_for(
            "document.querySelector('section[aria-label=\"Engagement metrics\"] article')?.innerText.includes('18')",
            "successful manual retry",
        )
        assert state["month_request_count"] > month_count_at_error, state["month_request_count"]
        assertions.append("manual retry recovers successfully without an automatic retry loop")
        print("PASS manual retry recovers")

        # The auth client makes a refresh request after a 401. Both the insight
        # request and that refresh remain synthetic, yielding an explicit
        # expired-session state and a sign-in path.
        state["expire_session"] = True
        await browser.evaluate("document.querySelector('button[aria-label=\"Refresh insights\"]')?.click()")
        await browser.wait_for(
            "document.querySelector('[role=\"alert\"]')?.innerText.includes('session has expired')",
            "the expired-session message",
        )
        expired = await browser.evaluate("""(() => ({
            alert: document.querySelector('[role="alert"]')?.innerText,
            signInHref: document.querySelector('[role="alert"] a[href="/provider/login"]')?.getAttribute('href')
        }))()""")
        assert expired["signInHref"] == "/provider/login", expired
        assertions.append("expired sessions produce explicit recovery guidance and a provider sign-in link")
        print("PASS expired-session state and sign-in recovery link")

        api_requests = [item for item in state["requests"] if item["path"].startswith("/api/")]
        assert api_requests and all(item["path"].startswith("/api/") for item in api_requests)
        assert not state["unexpected_api_requests"], state["unexpected_api_requests"]
        report["api_requests_intercepted"] = len(api_requests)
        report["assertions"] = assertions
        report["result"] = "passed"
        evidence_path = SCREENSHOTS / "provider-insights-browser-check.json"
        evidence_path.write_text(json.dumps(report, indent=2) + "\n")
        print("PASS all provider insights browser assertions; no API requests reached the app.")
        print(json.dumps(report, indent=2))
    finally:
        await browser.close()
        if launched_process is not None:
            launched_process.terminate()
            try:
                launched_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                launched_process.kill()
                launched_process.wait()
        if profile_dir:
            shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())