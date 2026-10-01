"""Synthetic browser smoke checks for provider portal access.

All /api/v1 requests are intercepted by Chrome DevTools Protocol and receive
synthetic responses, so this script never changes application database data.
Start the app and a dedicated Chromium CDP instance before running:

    chromium --headless --no-sandbox --remote-debugging-port=9223 \
      --user-data-dir=/tmp/provider-access-browser about:blank
    python3 scripts/check-provider-access-browser.py
"""
import asyncio
import base64
import json
import re
import urllib.parse
from pathlib import Path
from urllib.request import urlopen

import websockets


CDP_PORT = 9223
APP_URL = "http://127.0.0.1:5000"
SCREENSHOTS = Path("screenshots")
INVITATION_TYPES = ("DOCTOR", "CLINIC", "HOSPITAL")


class Browser:
    def __init__(self, websocket_url):
        self.websocket_url = websocket_url
        self.ws = None
        self.pending = {}
        self.handlers = []
        self.counter = 0
        self.reader = None

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
                if future is not None:
                    future.set_result(message)
            elif message.get("method") == "Fetch.requestPaused":
                for handler in self.handlers:
                    asyncio.create_task(handler(message["params"]))

    async def call(self, method, params=None):
        self.counter += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.counter] = future
        await self.ws.send(json.dumps({
            "id": self.counter,
            "method": method,
            "params": params or {},
        }))
        result = await asyncio.wait_for(future, timeout=15)
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
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")

    async def wait_for(self, expression, description, timeout=12):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if await self.evaluate(expression):
                return
            await asyncio.sleep(0.2)
        body = await self.evaluate("document.body.innerText")
        raise AssertionError(f"Timed out waiting for {description}.\n{body}")

    async def wait_for_state(self, predicate, description, timeout=12):
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.1)
        raise AssertionError(f"Timed out waiting for {description}.")

    async def click_text(self, text):
        clicked = await self.evaluate(
            "(() => { const target = [...document.querySelectorAll('button,a')].find("
            f"element => element.innerText.trim() === {json.dumps(text)}); "
            "if (!target) return false; target.click(); return true; })()"
        )
        assert clicked, f"Could not find clickable text: {text}"
        await asyncio.sleep(0.25)

    async def click_aria(self, label):
        clicked = await self.evaluate(
            "(() => { const target = document.querySelector("
            f"{json.dumps(f'button[aria-label=\"{label}\"]')}); "
            "if (!target) return false; target.click(); return true; })()"
        )
        assert clicked, f"Could not find button labeled: {label}"
        await asyncio.sleep(0.15)

    async def set_input(self, selector, value):
        expression = (
            "(() => { const input = document.querySelector("
            f"{json.dumps(selector)}); if (!input) return false; "
            "const setter = Object.getOwnPropertyDescriptor("
            "HTMLInputElement.prototype, 'value').set; setter.call(input, "
            f"{json.dumps(value)}); input.dispatchEvent(new Event('input', "
            "{ bubbles: true })); input.dispatchEvent(new Event('change', "
            "{ bubbles: true })); return true; })()"
        )
        assert await self.evaluate(expression), f"Could not fill {selector}"
        await asyncio.sleep(0.12)

    async def set_label_input(self, label, value):
        expression = (
            "(() => { const label = [...document.querySelectorAll('label')].find("
            f"element => element.innerText.trim() === {json.dumps(label)}); "
            "const input = label && document.getElementById(label.htmlFor); "
            "if (!input) return false; const setter = Object.getOwnPropertyDescriptor("
            "HTMLInputElement.prototype, 'value').set; setter.call(input, "
            f"{json.dumps(value)}); input.dispatchEvent(new Event('input', "
            "{ bubbles: true })); input.dispatchEvent(new Event('change', "
            "{ bubbles: true })); return true; })()"
        )
        assert await self.evaluate(expression), f"Could not fill field labeled {label}"
        await asyncio.sleep(0.12)

    async def navigate(self, path):
        await self.call("Page.navigate", {"url": f"{APP_URL}{path}"})
        await asyncio.sleep(0.5)

    async def viewport(self, width, height, mobile, filename):
        await self.call("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": mobile,
        })
        await asyncio.sleep(0.25)
        metrics = await self.evaluate("""(() => ({
            width: innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            bodyWidth: document.body.scrollWidth,
            height: innerHeight
        }))()""")
        assert metrics["documentWidth"] <= width and metrics["bodyWidth"] <= width, (
            f"Horizontal page overflow at {width}px: {metrics}"
        )
        shot = await self.call("Page.captureScreenshot", {"format": "png"})
        SCREENSHOTS.mkdir(exist_ok=True)
        (SCREENSHOTS / filename).write_bytes(base64.b64decode(shot["data"]))
        print(f"Captured {filename} ({width}x{height})")
        return metrics


async def main():
    targets = json.load(urlopen(f"http://127.0.0.1:{CDP_PORT}/json"))
    target = next((item for item in targets if item["type"] == "page"), targets[0])
    browser = Browser(target["webSocketDebuggerUrl"])
    browser_state = {
        "scenario": "public",
        "invitation_type": None,
        "approved": False,
        "requests": [],
        "draft_bodies": {},
        "submit_bodies": {},
        "reset_body": None,
        "setup_body": None,
        "login_body": None,
        "portal_access_posts": [],
        "approval_posts": [],
    }
    await browser.connect()
    browser.handlers.append(lambda params: intercept_request(browser, browser_state, params))

    async def command(method, params=None):
        return await browser.call(method, params)

    try:
        await command("Page.enable")
        await command("Runtime.enable")
        await command("Fetch.enable", {
            "patterns": [{"urlPattern": "*/api/v1/*", "requestStage": "Request"}]
        })

        # Invitation form credentials remain present for every provider type,
        # survive password toggles nowhere in drafts, and are sent only with a
        # final, valid submission.
        for provider_type in INVITATION_TYPES:
            browser_state["scenario"] = "public"
            browser_state["invitation_type"] = provider_type
            token = f"browser-{provider_type.lower()}-invitation"
            await browser.navigate(f"/provider/invitations/{token}")
            expected_heading = {
                "DOCTOR": "Complete your doctor profile",
                "CLINIC": "Complete your clinic profile",
                "HOSPITAL": "Complete your hospital profile",
            }[provider_type]
            await browser.wait_for(
                f"document.body.innerText.includes({json.dumps(expected_heading)})",
                f"{provider_type} invitation form",
            )
            await browser.wait_for(
                "!!document.querySelector('#invitation-password-confirmation')",
                f"{provider_type} invitation credentials",
            )
            types = await browser.evaluate("""({
                password: document.querySelector('#invitation-password')?.type,
                confirmation: document.querySelector('#invitation-password-confirmation')?.type,
                loginEmail: document.body.innerText.includes('provider-login@example.test')
            })""")
            assert types["password"] == "password" and types["confirmation"] == "password", types
            assert types["loginEmail"], f"Explicit login email missing: {provider_type}"
            await browser.viewport(
                1440, 900, False,
                f"provider-access-invitation-{provider_type.lower()}-desktop.png",
            )
            await browser.viewport(
                375, 812, True,
                f"provider-access-invitation-{provider_type.lower()}-mobile.png",
            )

            await browser.click_text("Save draft")
            await browser.wait_for_state(
                lambda: provider_type in browser_state["draft_bodies"],
                f"{provider_type} draft request",
            )
            draft = browser_state["draft_bodies"].get(provider_type)
            assert draft is not None, f"No draft payload captured for {provider_type}"
            assert "password" not in draft and "password_confirmation" not in draft, (
                f"{provider_type} draft leaked credentials: {draft.keys()}"
            )

            if provider_type == "DOCTOR":
                await browser.set_label_input("First name", "Casey")
                await browser.set_label_input("Last name", "Provider")
            else:
                await browser.set_label_input("Name", f"Browser {provider_type.title()}")
            await browser.set_input("#invitation-password", "BrowserPass9")
            await browser.set_input("#invitation-password-confirmation", "BrowserPass9")
            await browser.click_text("Submit for review")
            await browser.wait_for_state(
                lambda: provider_type in browser_state["submit_bodies"],
                f"{provider_type} final submission",
            )
            submitted = browser_state["submit_bodies"].get(provider_type)
            assert submitted is not None, f"No submit payload captured for {provider_type}"
            assert submitted.get("password") == "BrowserPass9", (
                f"{provider_type} final payload omitted invitation password"
            )
            assert submitted.get("password_confirmation") == "BrowserPass9", (
                f"{provider_type} final payload omitted password confirmation"
            )
            print(f"Invitation {provider_type}: credential fields present; drafts excluded secrets.")

        # Exercise the legacy first-password setup and the new reset flow. The
        # reset form enforces confirmation, toggles visibility, and links to
        # provider sign-in after a successful synthetic response.
        browser_state["scenario"] = "public"
        await browser.navigate("/provider/setup-password?token=synthetic-setup-token")
        await browser.wait_for(
            "document.body.innerText.includes('Set your password')",
            "provider setup-password form",
        )
        await browser.set_input("#portal-password", "BrowserSetupPass9")
        await browser.set_input("#portal-password-confirmation", "BrowserSetupPass9")
        await browser.click_text("Set password")
        await browser.wait_for(
            "document.body.innerText.includes('Password set')",
            "successful provider password setup",
        )
        assert browser_state["setup_body"] == {
            "token": "synthetic-setup-token",
            "password": "BrowserSetupPass9",
            "password_confirmation": "BrowserSetupPass9",
        }, browser_state["setup_body"]

        await browser.navigate("/provider/reset-password?token=synthetic-reset-token")
        await browser.wait_for(
            "document.body.innerText.includes('Reset your password')",
            "provider password-reset form",
        )
        await browser.viewport(
            1440, 900, False, "provider-access-reset-desktop.png"
        )
        await browser.viewport(
            375, 812, True, "provider-access-reset-mobile.png"
        )
        await browser.viewport(
            320, 700, True, "provider-access-reset-mobile-320.png"
        )

        await browser.set_input("#portal-password", "BrowserResetPass9")
        await browser.set_input("#portal-password-confirmation", "DifferentPass9")
        await browser.click_text("Reset password")
        await browser.wait_for(
            "document.body.innerText.includes('Passwords do not match.')",
            "password confirmation validation",
        )
        assert browser_state["reset_body"] is None, "Mismatched password unexpectedly submitted."
        await browser.click_aria("Show password")
        assert await browser.evaluate("document.querySelector('#portal-password').type") == "text"
        await browser.click_aria("Show password confirmation")
        assert await browser.evaluate(
            "document.querySelector('#portal-password-confirmation').type"
        ) == "text"
        await browser.click_aria("Hide password")
        await browser.click_aria("Hide password confirmation")
        await browser.set_input("#portal-password-confirmation", "BrowserResetPass9")
        await browser.click_text("Reset password")
        await browser.wait_for(
            "document.body.innerText.includes('Password reset')",
            "successful provider password reset",
        )
        assert browser_state["reset_body"] == {
            "token": "synthetic-reset-token",
            "password": "BrowserResetPass9",
            "password_confirmation": "BrowserResetPass9",
        }, browser_state["reset_body"]
        await browser.click_text("Go to provider sign in")
        await browser.wait_for(
            "!!document.querySelector('#provider-login-email')",
            "provider login page",
        )
        await browser.set_input("#provider-login-email", "provider-login@example.test")
        await browser.set_input("#provider-login-password", "BrowserResetPass9")
        await browser.click_text("Sign in to provider portal")
        await browser.wait_for(
            "location.pathname === '/provider/account'",
            "successful sign-in after reset",
        )
        assert browser_state["login_body"] == {
            "email": "provider-login@example.test",
            "password": "BrowserResetPass9",
        }, browser_state["login_body"]
        print("Setup/reset: confirmation, visibility controls, secure payloads, and sign-in passed.")

        # Synthetic admin list: approve an under-review provider and confirm
        # recipient-specific setup/reset mail before the admin dispatches it.
        browser_state["scenario"] = "admin"
        await browser.navigate("/admin/providers")
        await browser.wait_for(
            "!!document.querySelector('[aria-label=\"Actions for Review Clinic\"]')",
            "provider administration list",
        )
        await browser.viewport(
            1440, 900, False, "provider-access-admin-list-desktop.png"
        )
        await browser.viewport(
            375, 812, True, "provider-access-admin-list-mobile.png"
        )
        await browser.evaluate(
            "document.querySelector('[aria-label=\"Actions for Review Clinic\"]').click()"
        )
        await browser.click_text("Approve provider")
        await browser.wait_for(
            "document.body.innerText.includes('Provider portal account approved')",
            "provider approval result",
        )
        assert browser_state["approval_posts"] == ["/api/v1/admin/providers/review/approve"], (
            browser_state["approval_posts"]
        )

        await open_provider_action(browser, "Setup Clinic", "Send password setup email")
        await assert_access_confirmation(
            browser, "setup.owner@example.test", "Send password setup email?"
        )
        await browser.viewport(
            1440, 900, False, "provider-access-setup-confirm-desktop.png"
        )
        await browser.viewport(
            320, 700, True, "provider-access-setup-confirm-mobile-320.png"
        )
        await browser.click_text("Send setup email")
        await browser.wait_for(
            "document.body.innerText.includes('setup.owner@example.test')",
            "setup mail confirmation",
        )

        await open_provider_action(browser, "Reset Clinic", "Send password reset email")
        await assert_access_confirmation(
            browser, "reset.owner@example.test", "Send password reset email?"
        )
        await browser.click_text("Send reset email")
        await browser.wait_for(
            "document.body.innerText.includes('reset.owner@example.test')",
            "reset mail confirmation",
        )
        assert [entry["id"] for entry in browser_state["portal_access_posts"]] == [
            "setup", "reset"
        ], browser_state["portal_access_posts"]
        assert browser_state["portal_access_posts"][0]["body"] == {}
        assert browser_state["portal_access_posts"][1]["body"] == {}
        print("Admin list: approval plus explicit setup/reset recipient confirmations passed.")
        print("All provider-portal browser checks passed. Synthetic API only; no database writes.")
    finally:
        await browser.close()


async def open_provider_action(browser, provider_name, action_label):
    await browser.evaluate(
        f"document.querySelector('[aria-label=\"Actions for {provider_name}\"]').click()"
    )
    await browser.click_text(action_label)
    await browser.wait_for(
        "!!document.querySelector('[role=dialog]')",
        f"{provider_name} portal access dialog",
    )


async def assert_access_confirmation(browser, email, heading):
    body = await browser.evaluate("document.querySelector('[role=dialog]').innerText")
    assert heading in body and email in body, body


async def respond(browser, request_id, payload, status=200):
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    await browser.call("Fetch.fulfillRequest", {
        "requestId": request_id,
        "responseCode": status,
        "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
        "body": encoded,
    })


async def intercept_request(browser, state, params):
    request = params["request"]
    url = urllib.parse.urlparse(request["url"])
    path = url.path
    method = request["method"]
    body = {}
    if request.get("postData"):
        try:
            body = json.loads(request["postData"])
        except json.JSONDecodeError:
            body = {}
    state["requests"].append((method, path, body))
    data = {}
    status = 200

    if path == "/api/v1/auth/refresh":
        if state["scenario"] == "admin":
            data = login_response("admin", "browser-admin-token")
        else:
            data, status = {"detail": {"code": "no_refresh_token"}}, 401
    elif path == "/api/v1/admin/system-settings":
        data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
    elif path == "/api/v1/auth/login":
        state["login_body"] = body
        data = login_response("provider", "browser-provider-token")
    elif path == "/api/v1/provider/portal/profile":
        data, status = {"detail": {"message": "Synthetic browser profile unavailable."}}, 404
    elif path == "/api/v1/auth/provider-portal/setup-password":
        state["setup_body"] = body
        data = {"message": "Password set."}
    elif path == "/api/v1/auth/provider-portal/reset-password":
        state["reset_body"] = body
        data = {"message": "Password reset."}
    elif path.startswith("/api/v1/provider/invitations/"):
        suffix = path.removeprefix("/api/v1/provider/invitations/")
        if suffix.endswith("/specializations"):
            data = {"data": []}
        elif method == "GET":
            kind = state["invitation_type"] or "CLINIC"
            data = {
                "id": f"synthetic-{kind.lower()}-invitation",
                "provider_type": kind,
                "recipient_email": "provider-login@example.test",
                "emails_edited": False,
                "provider": {
                    "name": f"Browser {kind.title()}",
                    "first_name": "Casey",
                    "last_name": "Provider",
                    "visit_stability": "NOT_STABLE_VISIT",
                    "specializations": [],
                    "locations": [],
                    "phones": [],
                    "emails": [],
                    "photos": [],
                },
            }
        elif method == "POST" and suffix.endswith("/save"):
            token = suffix.removesuffix("/save")
            kind = state["invitation_type"] or "CLINIC"
            state["draft_bodies"][kind] = body
            data = {
                "id": f"synthetic-{kind.lower()}-invitation",
                "provider_type": kind,
                "recipient_email": "provider-login@example.test",
                "emails_edited": False,
                "provider": {"name": f"Browser {kind.title()}", "visit_stability": "NOT_STABLE_VISIT"},
            }
        elif method == "POST" and suffix.endswith("/submit"):
            kind = state["invitation_type"] or "CLINIC"
            state["submit_bodies"][kind] = body
            data = {
                "id": f"synthetic-{kind.lower()}-invitation",
                "provider_type": kind,
                "recipient_email": "provider-login@example.test",
                "emails_edited": False,
                "provider": {"name": f"Browser {kind.title()}", "visit_stability": "NOT_STABLE_VISIT"},
            }
    elif path == "/api/v1/admin/providers" and method == "GET":
        data = {
            "data": provider_fixtures(),
            "meta": {"page": 1, "page_size": 10, "total": 3, "total_pages": 1},
        }
    elif re.fullmatch(r"/api/v1/admin/providers/review/approve", path):
        state["approval_posts"].append(path)
        data = {"message": "Provider portal account approved.", "email_sent": True}
    elif re.fullmatch(r"/api/v1/admin/providers/(setup|reset)/portal-access", path):
        access_type = "setup" if "/setup/" in path else "reset"
        state["portal_access_posts"].append({"id": access_type, "body": body})
        data = {
            "message": f"Password {access_type} email sent to "
            f"{'setup.owner@example.test' if access_type == 'setup' else 'reset.owner@example.test'}.",
            "action": access_type,
            "available": True,
        }
    else:
        # Unknown API calls get a synthetic 404 rather than touching the app DB.
        data, status = {"detail": {"message": "Unmocked synthetic browser endpoint."}}, 404

    await respond(browser, params["requestId"], data, status)


def login_response(role, token):
    name = "Browser Provider" if role == "provider" else "Browser Admin"
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 900,
        "user": {
            "id": f"browser-{role}",
            "email": "provider-login@example.test" if role == "provider" else "admin@example.test",
            "first_name": "Browser",
            "last_name": role.title(),
            "full_name": name,
            "role": role,
            "roles": [role],
            "is_active": True,
            "email_verified_at": "2026-10-01T00:00:00Z",
            "last_successful_login_at": None,
        },
    }


def provider_fixtures():
    timestamp = "2026-10-01T00:00:00Z"
    common = {
        "provider_type": "CLINIC",
        "email": None,
        "phone": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "emergency_services_available": False,
        "publication_status": "UNPUBLISHED",
        "created_at": timestamp,
        "updated_at": timestamp,
        "thumbnail_url": None,
        "average_rating": None,
        "review_count": 0,
        "approval_available": False,
        "portal_access_reason": None,
        "portal_access_status": None,
    }
    return [
        {
            **common,
            "id": "review",
            "name": "Review Clinic",
            "status": "UNDER_REVIEW",
            "approval_available": True,
            "portal_access_action": None,
            "portal_login_email": None,
        },
        {
            **common,
            "id": "setup",
            "name": "Setup Clinic",
            "status": "ACTIVE",
            "portal_access_action": "setup",
            "portal_access_status": "invitation",
            "portal_access_reason": "Send a first-password setup link to the invitation login email.",
            "portal_login_email": "setup.owner@example.test",
        },
        {
            **common,
            "id": "reset",
            "name": "Reset Clinic",
            "status": "ACTIVE",
            "portal_access_action": "reset",
            "portal_access_status": "active",
            "portal_login_email": "reset.owner@example.test",
        },
    ]


asyncio.run(main())