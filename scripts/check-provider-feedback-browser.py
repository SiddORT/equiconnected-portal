"""Isolated provider feedback checks against synthetic API fixtures only.

Run against the existing Frontend workflow:
    python scripts/check-provider-feedback-browser.py
Screenshots use a temporary directory, never production/member data.
"""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

spec = importlib.util.spec_from_file_location(
    "feedback_browser_helpers", Path(__file__).with_name("check-provider-insights-browser.py")
)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


async def main():
    host = f"https://{os.environ['REPLIT_DEV_DOMAIN']}"
    output = Path(tempfile.mkdtemp(prefix="provider-feedback-check-"))
    helpers.SCREENSHOTS = output
    profile_dir = tempfile.mkdtemp(prefix="provider-feedback-chromium-")
    # Never attach to another check's browser/session.
    with socket.socket() as port_reservation:
        port_reservation.bind(("127.0.0.1", 0))
        helpers.CDP_PORT = port_reservation.getsockname()[1]
    process = subprocess.Popen([
        helpers.chromium_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", f"--remote-debugging-port={helpers.CDP_PORT}",
        f"--user-data-dir={profile_dir}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = None
    try:
        for _ in range(100):
            targets = helpers.browser_targets()
            if targets:
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError("Chromium failed to start")
        target = next(t for t in targets if t["type"] == "page")
        browser = helpers.Browser(target["webSocketDebuggerUrl"])
        await browser.connect()
        state = {"mode": "success", "unknown": [], "writes": []}
        user = {
            "id": "synthetic-provider", "email": "synthetic@example.test",
            "first_name": "Synthetic", "last_name": "Provider", "full_name": "Synthetic Provider",
            "role": "provider", "roles": ["provider"], "is_active": True,
            "email_verified_at": "2026-01-01T00:00:00Z",
        }
        editable = {
            "name": "Synthetic test clinic", "description": "Synthetic profile",
            "email": None, "phone": None, "website": None,
            "visit_stability": "NOT_STABLE_VISIT", "specialization_ids": [],
            "locations": [], "phones": [], "emails": [], "photos": [], "qualifications": [],
        }
        profile = {
            **editable, "id": "synthetic-listing", "specializations": [],
            "doctor_profile": None, "doctor_fields_available": False,
            "doctor_availability": None, "doctor_visits": [], "can_schedule_visits": False,
            "average_rating": 4.5, "review_count": 4, "visible_reviews": [],
            "editable_profile": editable, "profile_update": None,
        }

        async def intercept(params):
            request = params["request"]
            path = urlparse(request["url"]).path
            if not path.startswith("/api/"):
                await browser.call("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            status = 200
            body = {}
            method = request["method"]
            if method not in ("GET", "HEAD") and path != "/api/v1/auth/refresh":
                state["writes"].append(path)
            if path == "/api/v1/auth/refresh":
                body = {"access_token": "synthetic-only", "token_type": "bearer", "expires_in": 900, "user": user}
            elif path == "/api/v1/system-settings":
                body = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
            elif path == "/api/v1/messages/unread":
                body = {"count": 2}
            elif path == "/api/v1/messages/inbox":
                body = {"items": [], "page": 1, "page_size": 20, "total": 0}
            elif path == "/api/v1/provider/portal/profile":
                body = profile
            elif path == "/api/v1/provider/portal/specializations":
                body = []
            elif path == "/api/v1/provider/portal/feedback":
                if state["mode"] == "failure":
                    status = 503
                    body = {"detail": "Synthetic failure"}
                elif state["mode"] == "unavailable":
                    status = 403
                    body = {"detail": "Synthetic unavailable"}
                else:
                    page = int(parse_qs(urlparse(request["url"]).query).get("page", ["1"])[0])
                    rows = [{
                        "id": f"review-{index}", "rating": 5 - index,
                        "comment": "" if index == 1 else f"Synthetic {label.lower()} feedback.",
                        "reviewer_name": "Member A. R.", "created_at": "2026-10-01T12:34:00Z",
                        "status": label,
                    } for index, label in enumerate(["PENDING", "PUBLISHED", "REJECTED", "HIDDEN"])]
                    body = {"data": [] if state["mode"] == "empty" else rows if page == 1 else rows[-1:],
                            "meta": {"page": page, "page_size": 10, "total": 11, "total_pages": 2}}
            else:
                status = 501
                state["unknown"].append(path)
                body = {"detail": "Unmocked API blocked"}
            await browser.call("Fetch.fulfillRequest", {
                "requestId": params["requestId"], "responseCode": status,
                "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                "body": base64.b64encode(json.dumps(body).encode()).decode(),
            })

        browser.fetch_handler = intercept
        await browser.call("Page.enable")
        await browser.call("Runtime.enable")
        await browser.call("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
        await browser.call("Page.navigate", {"url": host + "/provider/feedback"})
        await browser.wait_for("document.body?.innerText.includes('Hidden by admin')", "all moderation states")
        assert await browser.evaluate("""(() => {
          const text = document.body.innerText;
          return ['Awaiting moderation','Published','Not published','Member A. R.','Rating only']
            .every(label => text.includes(label))
            && document.querySelector('a[href="/provider/feedback"]').getAttribute('aria-current') === 'page'
            && ![...document.querySelectorAll('button')].some(b => /reply|edit|delete|hide|restore/i.test(b.innerText));
        })()""")
        for width in (1440, 1024, 768, 640, 500, 430, 390, 320):
            await browser.viewport(width, 950, width < 640, f"feedback-{width}.jpg")
            assert await browser.evaluate("""[...document.querySelectorAll('nav[aria-label="Provider navigation"] a')]
              .every(a => { const r=a.getBoundingClientRect(); return r.width>0 && r.left>=0 && r.right<=innerWidth; })""")
        await browser.evaluate("document.querySelector('nav[aria-label=\"Provider navigation\"] a').focus()")
        for expected in ("Account", "Insights", "Member Feedback", "Messages"):
            assert expected in await browser.evaluate("document.activeElement.innerText")
            await browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
            await browser.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
        await browser.click_text("Next")
        await browser.wait_for("document.body?.innerText.includes('Page 2 of 2')", "next feedback page")
        await browser.click_text("Previous")
        await browser.wait_for("document.body?.innerText.includes('Page 1 of 2')", "previous feedback page")
        await browser.evaluate("document.querySelector('a[href=\"/provider/messages\"]').click()")
        await browser.wait_for(
            "document.querySelector('a[href=\"/provider/messages\"]').getAttribute('aria-current') === 'page' && !!document.querySelector('h1')",
            "existing Messages destination and active state",
        )
        for mode, text in (("failure", "Retry"), ("empty", "No feedback yet"), ("unavailable", "Feedback unavailable")):
            state["mode"] = mode
            await browser.call("Page.navigate", {"url": host + "/provider/feedback"})
            await browser.wait_for(f"document.body?.innerText.includes({json.dumps(text)})", mode)
            if mode == "failure":
                state["mode"] = "success"
                await browser.click_text("Retry")
                await browser.wait_for("document.body?.innerText.includes('Hidden by admin')", "retry recovery")
        await browser.call("Page.navigate", {"url": host + "/provider/account"})
        await browser.wait_for("!!document.querySelector('input[value=\"Synthetic test clinic\"]')", "account editor")
        name_selector = 'input[value="Synthetic test clinic"]'
        await browser.set_value(name_selector, "Synthetic unsaved edit")
        assert await browser.evaluate("""(() => {
          const link = [...document.querySelectorAll('a')].find(a => a.target === '_blank' && a.href.endsWith('/provider/feedback'));
          return !!link && link.innerText.includes('new tab') && !!document.querySelector('input[value="Synthetic unsaved edit"]');
        })()""")
        assert not state["unknown"], state["unknown"]
        assert not state["writes"], state["writes"]
        assert not browser.background_errors, browser.background_errors
        print("PASS feedback states, pagination, desktop/mobile navbar, keyboard order, Messages navigation, Account edit preservation; no API mutations")
        print(f"Synthetic screenshots: {output}")
    finally:
        if browser:
            await browser.close()
        process.terminate()
        process.wait(timeout=10)
        shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
