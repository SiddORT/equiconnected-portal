"""Browser-only visiting-calendar and directory invitation fixture check.

Uses a CDP-attached Chromium page and intercepted API fixtures only. No
credentials, database writes, or live API reads are used by this check.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets


CDP_PORT = 9222
TIME_ZONE = "UTC"
FIXTURE_PROVIDER_IDS = [f"browser-visiting-provider-{number}" for number in range(1, 6)]


def fixture_visits(today: date) -> list[dict]:
    remaining_days = (date(today.year, today.month + 1, 1) - today).days - 1 if today.month < 12 else (
        date(today.year + 1, 1, 1) - today
    ).days - 1
    busy_day = today + timedelta(days=min(2, remaining_days))
    providers = [
        ("Maple Equine Clinic", ["Equine dentistry", "Lameness"]),
        ("Cedar Veterinary Collective", ["Sports medicine"]),
        ("Willow Horse Health", ["Equine dentistry"]),
        ("Juniper Mobile Veterinary", ["Emergency care"]),
        ("Aspen Equine Specialists", ["Lameness", "Sports medicine"]),
    ]
    visits = []
    for index, (name, specializations) in enumerate(providers):
        start = busy_day - timedelta(days=1) if index == 3 else busy_day
        end = busy_day + timedelta(days=2) if index == 4 else busy_day
        visits.append({
            "id": f"browser-visit-{index + 1}",
            "provider_id": FIXTURE_PROVIDER_IDS[index],
            "provider_name": name,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "specializations": specializations,
            "location": {
                "name": f"{name} visiting service",
                "city": ["Austin", "Round Rock", "Georgetown", "Cedar Park", "Pflugerville"][index],
                "state_province": "Texas",
                "country": "United States",
            },
        })
    return visits


def member_provider_fixture() -> dict:
    return {
        "id": FIXTURE_PROVIDER_IDS[0],
        "is_saved": True,
        "provider_type": "DOCTOR",
        "name": "Maple Equine Clinic",
        "description": "Browser-only directory fixture.",
        "thumbnail_url": None,
        "thumbnail_alt_text": None,
        "website": None,
        "email": "maple@example.test",
        "phone": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "location": {"city": "Austin", "state_province": "Texas", "country": "United States"},
        "average_rating": None,
        "review_count": 0,
        "distance_km": None,
        "specializations": ["Equine dentistry", "Lameness"],
        "emergency_services_available": False,
    }


async def main():
    domain = os.environ.get("REPLIT_DEV_DOMAIN")
    if not domain:
        raise RuntimeError("Set REPLIT_DEV_DOMAIN to the already-running app host.")
    origin = f"https://{domain}"
    today = datetime.now(timezone.utc).date()
    visits = fixture_visits(today)
    busy_day = date.fromisoformat(visits[0]["start_date"])
    admin_stats = {
        "total_users": 17,
        "active_providers": 12,
        "provider_counts": {"hospitals": 2, "clinics": 4, "doctors": 6},
        "invitation_counts": {"sent": 3, "accepted": 2, "rejected": 1},
        "registration_counts": {
            "registrations": 5,
            "verified": 4,
            "unverified": 1,
            "horse_owners": 3,
            "stable_managers": 1,
        },
        "visitor_visits": [],
        "location_markers": [],
    }
    settings = {
        "timezone": TIME_ZONE,
        "date_format": "month_day_year",
        "time_format": "12_hour",
    }
    fixture_member_provider = member_provider_fixture()
    fixture_requests: list[dict] = []
    intercepted_app_posts: list[dict] = []
    browser_errors: list[dict] = []
    mock_role = "admin"
    current_route = ""
    launched_process = None
    profile_dir = None

    def stop_launched_browser():
        nonlocal launched_process, profile_dir
        if launched_process is not None:
            launched_process.terminate()
            try:
                launched_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                launched_process.kill()
                launched_process.wait()
            launched_process = None
        if profile_dir:
            shutil.rmtree(profile_dir, ignore_errors=True)
            profile_dir = None

    def browser_targets():
        try:
            with urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=1) as response:
                return json.load(response)
        except Exception:
            return None

    targets = browser_targets()
    if not targets:
        browser_binary = next(
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
        if not browser_binary:
            raise RuntimeError(
                "No CDP browser is listening on port 9222 and Chromium was not found."
            )
        profile_dir = tempfile.mkdtemp(prefix="visiting-calendar-cdp-")
        launched_process = subprocess.Popen(
            [
                browser_binary,
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
                stop_launched_browser()
                raise RuntimeError("The headless Chromium process exited before CDP became ready.")
            await asyncio.sleep(0.1)
        if not targets:
            stop_launched_browser()
            raise RuntimeError("Chromium did not open its CDP endpoint on port 9222.")

    page_target = next((item for item in targets if item.get("type") == "page"), None)
    if not page_target:
        stop_launched_browser()
        raise RuntimeError(f"No page target is available on CDP port {CDP_PORT}.")

    admin_visits = [
        {
            **visit,
            "location": {**visit["location"]},
        }
        for visit in visits
    ]
    member_visits = [
        {
            key: value
            for key, value in visit.items()
            if key != "location"
        } | {
            "location": {
                key: visit["location"][key]
                for key in ("city", "state_province", "country")
            }
        }
        for visit in visits
    ]
    month_data_admin = {"month": today.strftime("%Y-%m"), "today": today.isoformat(), "visits": admin_visits}
    month_data_member = {"month": today.strftime("%Y-%m"), "today": today.isoformat(), "visits": member_visits}

    async with websockets.connect(page_target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
        pending = {}
        counter = 0

        async def command(method, params=None):
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            result = await future
            if "error" in result:
                raise RuntimeError(result["error"])
            return result.get("result", {})

        async def fulfill(request_id, body, status=200):
            encoded = base64.b64encode(
                json.dumps(body, separators=(",", ":")).encode()
            ).decode() if body is not None else ""
            headers = [{"name": "Content-Type", "value": "application/json"}]
            await command(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": status,
                    "responseHeaders": headers,
                    "body": encoded,
                },
            )

        async def intercept(params):
            nonlocal mock_role
            request = params["request"]
            parsed = urlparse(request["url"])
            path = parsed.path
            method = request.get("method", "GET").upper()
            fixture_requests.append({"path": path, "method": method, "query": parsed.query})
            if method not in ("GET", "HEAD") and not path.endswith("/auth/refresh"):
                intercepted_app_posts.append({"path": path, "method": method})

            if path.endswith("/auth/refresh") or path.endswith("/auth/me"):
                if mock_role == "admin":
                    user = {
                        "id": "browser-visiting-calendar-admin",
                        "email": "calendar-admin@example.test",
                        "first_name": "Browser",
                        "last_name": "Admin",
                        "full_name": "Browser Calendar Admin",
                        "role": "admin",
                        "roles": ["admin"],
                    }
                else:
                    user = {
                        "id": "browser-visiting-calendar-member",
                        "email": "calendar-member@example.test",
                        "first_name": "Browser",
                        "last_name": "Member",
                        "full_name": "Browser Calendar Member",
                        "role": "horse_owner",
                        "roles": ["horse_owner"],
                    }
                user.update({
                    "is_active": True,
                    "email_verified_at": datetime.now(timezone.utc).isoformat(),
                    "last_successful_login_at": None,
                })
                response = (
                    {"access_token": "browser-only-visiting-calendar-fixture", "token_type": "bearer",
                     "expires_in": 3600, "user": user}
                    if path.endswith("/auth/refresh")
                    else user
                )
            elif path.endswith("/system-settings"):
                response = settings
            elif path.endswith("/admin/dashboard/stats"):
                response = admin_stats
            elif path.endswith("/admin/dashboard/visits"):
                response = month_data_admin
            elif path.endswith("/member/providers/visits/calendar"):
                response = month_data_member
            elif path.endswith("/member/providers/visits/availability"):
                # Deliberately directory-wide, irrespective of the active saved/name filters.
                response = {"has_visits": True}
            elif path.endswith("/member/providers/filters"):
                response = {"specializations": [], "regions": []}
            elif path.rstrip("/") == "/api/v1/member/providers":
                response = {
                    "data": [fixture_member_provider],
                    "meta": {"page": 1, "page_size": 10, "total": 1, "total_pages": 1},
                }
            elif path.rstrip("/") == "/api/v1/profile":
                response = {
                    "first_name": "Browser",
                    "last_name": "Member",
                    "email": "calendar-member@example.test",
                    "mobile_number": None,
                    "address": None,
                    "country": None,
                    "state_province": None,
                    "city": None,
                    "postal_code": None,
                    "roles": ["horse_owner"],
                    "stable_profile": None,
                    "horses": [],
                }
            elif path.endswith("/member/history/recent"):
                response = []
            elif method not in ("GET", "HEAD"):
                # Suppress analytics and any other mutation attempt; nothing reaches the app API.
                await fulfill(params["requestId"], None, status=204)
                return
            else:
                response = {}
            await fulfill(params["requestId"], response)

        async def handle_intercept(params):
            try:
                await intercept(params)
            except Exception as exc:
                browser_errors.append(
                    f"Fixture interception failed for {params.get('request', {}).get('url')}: "
                    f"{type(exc).__name__}: {exc}"
                )
                try:
                    await command("Fetch.failRequest", {
                        "requestId": params["requestId"],
                        "errorReason": "Failed",
                    })
                except Exception:
                    pass

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    future = pending.pop(message["id"], None)
                    if future and not future.done():
                        future.set_result(message)
                    continue
                method = message.get("method")
                params = message.get("params", {})
                if method == "Fetch.requestPaused":
                    asyncio.create_task(handle_intercept(params))
                elif method == "Runtime.exceptionThrown":
                    details = params.get("exceptionDetails", {})
                    browser_errors.append({
                        "route": current_route,
                        "text": details.get("text", "Browser exception"),
                        "description": details.get("exception", {}).get("description"),
                        "stack": details.get("stackTrace"),
                    })

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result.get("result", {}).get("value")

        async def wait_for(expression, description, timeout=25):
            for _ in range(timeout * 10):
                value = await evaluate(expression)
                if value:
                    return value
                await asyncio.sleep(0.1)
            body = await evaluate("document.body?.innerText ?? ''")
            raise AssertionError(
                f"Timed out waiting for {description}. Page text:\n{body}\n"
                f"Fixture requests: {json.dumps(fixture_requests[-12:], indent=2)}\n"
                f"Browser errors: {json.dumps(browser_errors, indent=2)}"
            )

        async def navigate(path, role):
            nonlocal mock_role, current_route
            mock_role = role
            current_route = path
            await command("Page.navigate", {"url": origin + path})
            await wait_for("document.readyState === 'complete'", f"document load for {path}", timeout=35)

        async def save_screenshot(name):
            result = await command(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": False},
            )
            directory = Path("screenshots")
            directory.mkdir(exist_ok=True)
            path = directory / name
            path.write_bytes(base64.b64decode(result["data"]))
            print(f"Saved screenshot: {path}")

        async def click(expression, description):
            assert await evaluate(expression), f"Could not find {description}."
            await asyncio.sleep(0.35)

        try:
            await command("Page.enable")
            await command("Runtime.enable")
            await command("Fetch.enable", {"patterns": [{"urlPattern": "*/api/v1/*"}]})
            await command("Emulation.setTimezoneOverride", {"timezoneId": TIME_ZONE})
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1300, "deviceScaleFactor": 1, "mobile": False},
            )

            # The admin dashboard contributes a fifth inventory card, but no inline schedule.
            await navigate("/admin/dashboard", "admin")
            await wait_for(
                "!!document.querySelector('#stats-heading')?.nextElementSibling",
                "admin dashboard stats",
            )
            dashboard_state = await wait_for(
                """(() => {
                  const cards=[...(document.querySelector('#stats-heading')?.nextElementSibling?.children ?? [])];
                  if(cards.length!==5)return null;
                  const rects=cards.map(card=>card.getBoundingClientRect());
                  return {
                    cards:cards.length,
                    tops:rects.map(rect=>Math.round(rect.top)),
                    lefts:rects.map(rect=>Math.round(rect.left)),
                    labels:cards.map(card=>card.innerText.trim()),
                    inlineCalendar:!!document.querySelector(
                      '[aria-label$=" dates"], button[aria-label="Previous month"]'
                    )
                  };
                })()""",
                "five-card dashboard layout",
            )
            assert len(set(dashboard_state["tops"])) == 1, dashboard_state
            assert dashboard_state["lefts"] == sorted(dashboard_state["lefts"]), dashboard_state
            assert not dashboard_state["inlineCalendar"], dashboard_state
            assert not any(item["path"].endswith("/admin/dashboard/visits") for item in fixture_requests), \
                "Dashboard fetched calendar visits instead of keeping the schedule off-page."
            await save_screenshot("visiting-calendar-admin-dashboard.png")

            # Admin full calendar: select the intentionally crowded day and inspect destinations.
            await navigate("/admin/visiting-providers", "admin")
            await wait_for(
                "document.body.innerText.includes('SCHEDULE') && "
                "document.body.innerText.includes(" + json.dumps(today.strftime("%B %Y")) + ")",
                "admin visiting calendar",
            )
            admin_visits_before = sum(
                item["path"].endswith("/admin/dashboard/visits") for item in fixture_requests
            )
            assert admin_visits_before > 0, "Admin calendar did not load its visiting schedule fixture."
            long_busy_date = f"{busy_day.strftime('%A, %B')} {busy_day.day}, {busy_day.year}"
            busy_button_label = f"{long_busy_date}, 5 visiting providers"
            await click(
                "(() => { const target=" + json.dumps(busy_button_label) +
                "; const day=[...document.querySelectorAll('button[aria-label]')].find("
                "button=>button.getAttribute('aria-label')===target);"
                "if(!day)return false;day.click();return true; })()",
                "crowded admin calendar day",
            )
            admin_agenda = await wait_for(
                "document.querySelectorAll('a[href*=\"browser-visiting-provider-\"]').length===5 && "
                "[...document.querySelectorAll('button[aria-label]')].some(button=>"
                "button.getAttribute('aria-label')===" + json.dumps(busy_button_label) +
                "&&button.getAttribute('aria-pressed')==='true')",
                "five-provider admin day agenda",
            )
            admin_links = await evaluate(
                "[...document.querySelectorAll('a[href*=\"browser-visiting-provider-\"]')].map(link=>link.getAttribute('href'))"
            )
            assert len(admin_links) == 5 and all(
                link and link.startswith("/admin/providers/") for link in admin_links
            ), admin_links
            assert len(set(admin_links)) == 5, admin_links
            await save_screenshot("visiting-calendar-admin-calendar-desktop.png")

            # Directory invitation remains available with active name/saved filters.
            directory_path = "/providers?name=Maple&saved=true"
            await navigate(directory_path, "member")
            await wait_for(
                "!!document.querySelector('[aria-label=\"Directory-wide visiting providers\"]') && "
                "!!document.querySelector('[aria-label=\"Directory-wide visiting providers\"] a')",
                "directory-wide visiting invitation",
            )
            await wait_for(
                "document.querySelector('[aria-label=\"Directory-wide visiting providers\"]')?.innerText"
                ".includes('See our esteemed visiting providers')",
                "directory-wide availability fixture",
            )
            directory_state = await evaluate("""(() => {
              const invitation=document.querySelector('[aria-label="Directory-wide visiting providers"]');
              const link=invitation?.querySelector('a');
              return {
                invitation:invitation?.innerText ?? '',
                href:link?.getAttribute('href') ?? null,
                currentQuery:location.search,
                name:document.querySelector('#provider-name-filter')?.value ?? null,
                saved:document.querySelector('h1')?.innerText.includes('Saved providers') ?? false
              };
            })()""")
            assert directory_state["href"] == "/providers/visiting-calendar?name=Maple&saved=true", directory_state
            assert directory_state["currentQuery"] == "?name=Maple&saved=true", directory_state
            assert directory_state["name"] == "Maple" and directory_state["saved"], directory_state
            assert any(
                item["path"].endswith("/member/providers/visits/availability")
                for item in fixture_requests
            ), "Directory-wide invitation did not request its availability endpoint."
            list_requests = [
                item for item in fixture_requests
                if item["path"].rstrip("/") == "/api/v1/member/providers"
            ]
            assert list_requests and all(
                "name=Maple" in item["query"] and "saved_only=true" in item["query"]
                for item in list_requests
            ), list_requests

            await click(
                "(() => { const link=document.querySelector('[aria-label=\"Directory-wide visiting providers\"] a');"
                "if(!link)return false;link.click();return true; })()",
                "member calendar invitation link",
            )
            await wait_for(
                "location.pathname==='/providers/visiting-calendar' && "
                "location.search==='?name=Maple&saved=true' && document.body.innerText.includes('SCHEDULE')",
                "member calendar route with preserved directory query",
            )
            await wait_for(
                "document.body.innerText.includes(" + json.dumps(today.strftime("%B %Y")) + ")",
                "member visiting calendar",
            )
            await click(
                "(() => { const target=" + json.dumps(busy_button_label) +
                "; const day=[...document.querySelectorAll('button[aria-label]')].find("
                "button=>button.getAttribute('aria-label')===target);"
                "if(!day)return false;day.click();return true; })()",
                "crowded member calendar day",
            )
            await wait_for(
                "document.querySelectorAll('a[href*=\"browser-visiting-provider-\"]').length===5 && "
                "[...document.querySelectorAll('button[aria-label]')].some(button=>"
                "button.getAttribute('aria-label')===" + json.dumps(busy_button_label) +
                "&&button.getAttribute('aria-pressed')==='true')",
                "five-provider member day agenda",
            )
            member_links = await evaluate(
                "[...document.querySelectorAll('a[href*=\"browser-visiting-provider-\"]')].map(link=>link.getAttribute('href'))"
            )
            assert len(member_links) == 5 and all(
                link and link.startswith("/providers/") and "name=Maple&saved=true" in link
                for link in member_links
            ), member_links
            assert len(set(member_links)) == 5, member_links
            return_href = await evaluate(
                "[...document.querySelectorAll('a')].find(link=>link.innerText.includes('Provider directory'))"
                "?.getAttribute('href') ?? null"
            )
            assert return_href == "/providers?name=Maple&saved=true", return_href
            assert any(
                item["path"].endswith("/member/providers/visits/calendar")
                for item in fixture_requests
            ), "Member calendar did not request its visits fixture."
            await save_screenshot("visiting-calendar-member-desktop.png")

            # Narrow device emulation checks both overflow and agenda legibility.
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
            )
            mobile_state = await evaluate("""(() => {
              const cards=[...document.querySelectorAll('a[href*="browser-visiting-provider-"]')];
              const selectedDay=[...document.querySelectorAll('button[aria-label]')].find(
                button=>button.getAttribute('aria-label')===""" + json.dumps(busy_button_label) + """);
              const mobileDay=[...document.querySelectorAll('button[aria-pressed]')].find(
                button=>button.innerText.includes('5 providers'));
              const desktopCalendar=selectedDay?.parentElement?.parentElement;
              const agenda=document.querySelector('#agenda-heading')?.closest('aside');
              const fonts=cards.map(card=>parseFloat(getComputedStyle(card.querySelector('strong')).fontSize));
              const rects=cards.map(card=>card.getBoundingClientRect());
              return {
                viewport:window.innerWidth,
                documentWidth:document.documentElement.scrollWidth,
                bodyWidth:document.body.scrollWidth,
                desktopCalendarDisplay:desktopCalendar ? getComputedStyle(desktopCalendar).display : 'missing',
                mobileAgendaDisplay:mobileDay?.parentElement ? getComputedStyle(mobileDay.parentElement).display : 'missing',
                agendaWidth:agenda?.getBoundingClientRect().width ?? 0,
                cards:cards.length,
                fonts,
                cardWidths:rects.map(rect=>Math.round(rect.width)),
                cardRights:rects.map(rect=>Math.round(rect.right))
              };
            })()""")
            assert mobile_state["viewport"] == 390, mobile_state
            assert mobile_state["documentWidth"] <= 390 and mobile_state["bodyWidth"] <= 390, mobile_state
            assert mobile_state["desktopCalendarDisplay"] == "none", mobile_state
            assert mobile_state["mobileAgendaDisplay"] != "none" and mobile_state["agendaWidth"] > 0, mobile_state
            assert mobile_state["cards"] == 5 and all(size >= 14 for size in mobile_state["fonts"]), mobile_state
            assert all(width > 0 for width in mobile_state["cardWidths"]), mobile_state
            assert all(right <= 390 for right in mobile_state["cardRights"]), mobile_state
            await evaluate("document.querySelector('#agenda-heading')?.scrollIntoView({block:'start'})")
            await asyncio.sleep(0.25)
            await save_screenshot("visiting-calendar-member-mobile-390.png")

            # The agenda return action must restore both URL filters exactly.
            await click(
                "(() => { const link=[...document.querySelectorAll('a')].find(item=>item.innerText.includes('Provider directory'));"
                "if(!link)return false;link.click();return true; })()",
                "calendar return-to-directory link",
            )
            await wait_for(
                "location.pathname==='/providers' && location.search==='?name=Maple&saved=true' && "
                "!!document.querySelector('[aria-label=\"Directory-wide visiting providers\"]')",
                "directory query after returning from calendar",
            )
            assert await evaluate("document.querySelector('#provider-name-filter')?.value") == "Maple"
            assert not browser_errors, browser_errors
            assert all(
                request["path"].startswith("/api/v1/")
                for request in fixture_requests
            ), "An API request escaped the synthetic API fixture interceptor."
            assert all(
                request["path"] in (
                    "/api/v1/member/history",
                    "/api/v1/member/providers/traffic-view",
                )
                and request["method"] == "POST"
                for request in intercepted_app_posts
            ), intercepted_app_posts

            evidence = {
                "fixture_data_only": True,
                "database_or_live_api_writes": False,
                "intercepted_application_analytics_posts_suppressed": intercepted_app_posts,
                "admin_dashboard": dashboard_state,
                "busy_day": busy_day.isoformat(),
                "admin_profile_destinations": admin_links,
                "member_profile_destinations": member_links,
                "directory_invitation": directory_state,
                "directory_return_href": return_href,
                "member_mobile_390": mobile_state,
                "fixture_api_requests": fixture_requests,
                "browser_errors": browser_errors,
                "screenshots": [
                    "screenshots/visiting-calendar-admin-dashboard.png",
                    "screenshots/visiting-calendar-admin-calendar-desktop.png",
                    "screenshots/visiting-calendar-member-desktop.png",
                    "screenshots/visiting-calendar-member-mobile-390.png",
                ],
            }
            evidence_path = Path("screenshots/visiting-calendar-browser-check.json")
            evidence_path.write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence, indent=2))
            print("Visiting calendar browser fixture checks passed.")
        finally:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass
            stop_launched_browser()


asyncio.run(main())