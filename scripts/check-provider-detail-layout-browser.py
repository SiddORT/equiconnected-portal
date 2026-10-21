"""Provider detail layout checks using fail-closed synthetic API fixtures.

Start the Frontend workflow, then run:
  chromium --headless --no-sandbox --disable-gpu --remote-debugging-port=9224 \
    --user-data-dir=/tmp/provider-detail-layout-browser about:blank
  python3 scripts/check-provider-detail-layout-browser.py

No real authentication, email delivery, or database records are used.
Screenshots and measured results go to ignored generated-artifacts/.
"""
import asyncio
import base64
import importlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

helpers = importlib.import_module("check-provider-access-browser")
OUTPUT = Path("generated-artifacts/provider-detail-layout")
GUIDANCE = "A password reset link can be sent to the linked provider login email."
ORIGIN = "https://" + os.environ["REPLIT_DEV_DOMAIN"]


def fixture(kind, populated):
    long_value = "synthetic-" + "x" * 95
    location = {
        "id": "location-1", "name": "Synthetic paddock",
        "address_line_1": long_value, "city": "Synthetic City", "country": "Canada",
        "is_primary": True, "latitude": None, "longitude": None,
    }
    return {
        "id": "synthetic-layout", "provider_type": kind,
        "name": f"Synthetic {kind.title()} — Layout Fixture",
        "description": "Synthetic listing for isolated layout checks only.",
        "email": long_value + "@example.test" if populated else None,
        "phone": "+1 555 0100" if populated else None,
        "website": "https://example.test/" + long_value if populated else None,
        "status": "ACTIVE", "publication_status": "PUBLISHED",
        "visit_stability": "STABLE_VISIT", "years_experience": 10,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "languages": [{"id": str(i), "name": name, "code": str(i), "is_active": True}
                      for i, name in enumerate(["Arabic", "English", "French", "German", "Japanese",
                                                "Korean", "Portuguese", "Russian", long_value])] if populated else [],
        "specializations": [{"id": "spec-1", "name": long_value, "is_active": True}] if populated else [],
        "locations": [location, {**location, "id": "location-2", "is_primary": False}] if populated else [],
        "photos": [{
            "id": "photo-1", "storage_reference": "synthetic-placeholder",
            "caption": long_value, "alt_text": long_value, "is_thumbnail": True,
        }] if populated else [],
        "emails": [], "phones": [], "thumbnail_url": None,
        "maximum_working_radius_km": 100, "clinic_hospital_visit": False,
        "emergency_services_available": populated, "emergency_contact_name": long_value,
        "emergency_contact_number": "+1 555 0100", "doctor_availability": "VISITING",
        "doctor_profile": {
            "first_name": "Synthetic", "last_name": "Doctor", "professional_title": long_value,
            "biography": long_value, "experience_description": "Synthetic experience notes",
        } if populated else None,
        "qualifications": [{
            "id": "qualification-1", "title": long_value, "institution": long_value,
            "year_obtained": 2020, "description": long_value,
        }] if populated else [],
        "doctor_visits": [{
            "id": "visit-1", "location": location, "start_date": "2999-01-01", "end_date": "2999-01-02",
        }] if populated else [],
        "organizations": [],
    }


def access(state):
    return {
        "status": "active", "action": "reset", "available": True,
        "message": state.get("confirmation") or GUIDANCE,
        "reason": " \n" + (state.get("confirmation") or GUIDANCE) + " ",
        "recipient_email": "synthetic-" + "r" * 90 + "@example.test",
        "email_id": None, "invitation_id": None, "sent_at": None,
        "selectable_emails": [], "can_revoke": False,
    }


async def main():
    target = next(t for t in json.load(urlopen("http://127.0.0.1:9224/json")) if t["type"] == "page")
    browser = helpers.Browser(target["webSocketDebuggerUrl"])
    state = {"provider": fixture("CLINIC", True), "confirmation": None, "fail": False}
    unexpected, requests, handler_errors = [], [], []
    await browser.connect()

    async def intercept(params):
        try:
            request = params["request"]
            url = urlparse(request["url"])
            path, method = url.path, request["method"]
            # API classification precedes the static resource allow-list.
            if not path.startswith("/api/"):
                if url.hostname in ("fonts.googleapis.com", "fonts.gstatic.com"):
                    await browser.call("Fetch.continueRequest", {"requestId": params["requestId"]})
                    return
                if request["url"].startswith(ORIGIN + "/") and (
                    path.startswith(("/src/", "/node_modules/", "/@vite/", "/@id/", "/@react-refresh", "/assets/", "/fonts/"))
                    or path in ("/", "/admin/providers/synthetic-layout", "/favicon.ico", "/favicon.png", "/logo.png", "/vite.svg")
                ):
                    await browser.call("Fetch.continueRequest", {"requestId": params["requestId"]})
                    return
                unexpected.append((method, request["url"]))
                await browser.call("Fetch.failRequest", {"requestId": params["requestId"], "errorReason": "BlockedByClient"})
                return
            requests.append((method, path))
            status = 200
            if path == "/api/v1/auth/refresh":
                payload = helpers.login_response("admin", "synthetic-layout-token")
            elif path in ("/api/v1/system-settings", "/api/v1/admin/system-settings"):
                payload = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
            elif path in ("/api/v1/admin/providers/synthetic-layout", "/api/v1/admin/doctors/synthetic-layout"):
                assert method == "GET"
                payload = state["provider"]
            elif path == "/api/v1/admin/specializations":
                payload = {"data": [], "meta": {"page": 1, "page_size": 100, "total": 0, "total_pages": 1}}
            elif path == "/api/v1/admin/providers/synthetic-layout/portal-access":
                if method == "POST" and state["fail"]:
                    payload, status = {"detail": {"message": "Synthetic delivery unavailable."}}, 503
                else:
                    if method == "POST":
                        state["confirmation"] = "Password reset email sent to the synthetic login."
                    payload = access(state)
            else:
                unexpected.append((method, request["url"]))
                payload, status = {"detail": "Unconfigured synthetic route"}, 501
            await helpers.respond(browser, params["requestId"], payload, status)
        except Exception as exc:
            handler_errors.append(str(exc))
            await browser.call("Fetch.failRequest", {"requestId": params["requestId"], "errorReason": "BlockedByClient"})

    browser.handlers.append(intercept)
    results = []
    try:
        await browser.call("Page.enable")
        await browser.call("Runtime.enable")
        await browser.call("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for kind in ("CLINIC", "HOSPITAL", "DOCTOR"):
            for populated in (True, False):
                state.update(provider=fixture(kind, populated), confirmation=None, fail=False)
                await browser.call("Page.navigate", {"url": ORIGIN + "/admin/providers/synthetic-layout"})
                await browser.wait_for(
                    "document.body.innerText.includes('Services & languages') && document.body.innerText.includes("
                    + json.dumps(GUIDANCE) + ")", "synthetic provider detail")
                if kind == "DOCTOR":
                    await browser.wait_for("document.body.innerText.includes('Qualifications')", "doctor qualifications")
                for width in (1440, 375, 320):
                    await browser.call("Emulation.setDeviceMetricsOverride", {
                        "width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": width < 500,
                    })
                    await asyncio.sleep(.2)
                    measured = await browser.evaluate("""(() => {
                      const card = name => [...document.querySelectorAll('h2')].find(e=>e.textContent===name)
                        .closest('[class*="card--pad"]');
                      const names = ['Overview','Provider portal access','Services & languages','Specializations','Locations','Photos'];
                      if (document.body.innerText.includes('Professional info')) names.push('Professional info','Qualifications','Doctor trips');
                      const rect = e => e.getBoundingClientRect();
                      return {width:innerWidth, documentWidth:document.documentElement.scrollWidth,
                        guidanceCount:[...document.querySelectorAll('p')].filter(e=>e.textContent.trim()===
                          'A password reset link can be sent to the linked provider login email.').length,
                        cards:names.map(name=>{
                          const c=card(name), h=c.querySelector('[class*="cardHeader"]'), dl=c.querySelector('dl');
                          const headerContent = h?.firstElementChild ?? c.querySelector('h2');
                          const bodyContent = dl ?? c.querySelector('[class*="cardBody"]')?.firstElementChild;
                          return {name,left:rect(c).left,right:rect(c).right,
                            headerBorder:h ? getComputedStyle(h).borderBottomWidth : null,
                            stripBorder:dl ? getComputedStyle(dl).borderTopWidth : null,
                            insetAligned:!bodyContent || Math.abs(rect(headerContent).left-rect(bodyContent).left)<1,
                            fits:[...c.querySelectorAll('dd,button,p,[class*="itemMain"],[class*="pill"]')]
                              .every(e=>e.scrollWidth<=e.clientWidth+1 && rect(e).right<=rect(c).right+1),
                            rowBorders:[...c.querySelectorAll('li[class*="item_"]')].map(e=>getComputedStyle(e).borderBottomWidth)};
                        })};
                    })()""")
                    assert measured["documentWidth"] <= width, measured
                    assert measured["guidanceCount"] == 1, measured
                    for card in measured["cards"]:
                        assert card["fits"] and card["insetAligned"], card
                        if card["name"] == "Overview":
                            assert card["stripBorder"] == "1px", card
                        else:
                            assert card["headerBorder"] == "1px", card
                            assert card["stripBorder"] in (None, "0px"), card
                        if card["rowBorders"]:
                            assert card["rowBorders"][-1] == "0px", card
                            assert all(v == "1px" for v in card["rowBorders"][:-1]), card
                    full = [c for c in measured["cards"] if c["name"] in ("Overview", "Provider portal access", "Services & languages")]
                    assert len({(c["left"], c["right"]) for c in full}) == 1, full
                    results.append({"kind": kind, "populated": populated, **measured})
                    # Capture the whole genuine shipped screen, not a recreated mockup.
                    metrics = await browser.call("Page.getLayoutMetrics")
                    height = metrics["cssContentSize"]["height"]
                    shot = await browser.call("Page.captureScreenshot", {
                        "format": "png", "captureBeyondViewport": True,
                        "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
                    })
                    label = f"{kind.lower()}-{'populated' if populated else 'empty'}-{width}.png"
                    (OUTPUT / label).write_bytes(base64.b64decode(shot["data"]))
                print(f"{kind} {'populated' if populated else 'empty'}: dividers, insets, wrapping, row borders, overflow passed.")
        # Actual browser action failure and success, with a refreshed duplicate confirmation.
        state.update(fail=True)
        await browser.click_text("Send password reset email")
        await browser.wait_for("document.body.innerText.includes('Delivery is not confirmed.')", "send failure")
        state.update(fail=False)
        await browser.click_text("Send password reset email")
        await browser.wait_for("document.body.innerText.includes('Password reset email sent to the synthetic login.')"
                               " && !document.body.innerText.includes('Loading portal access status')", "send success")
        assert await browser.evaluate("""[...document.querySelectorAll('p')].filter(e=>
          e.textContent.trim()==='Password reset email sent to the synthetic login.').length""") == 1
        assert not unexpected, unexpected
        assert not handler_errors, handler_errors
        (OUTPUT / "measurements.json").write_text(json.dumps({"results": results, "requests": requests}, indent=2))
        print("All 18 synthetic layout cases and reset feedback checks passed. No live API requests.")
    finally:
        if unexpected or handler_errors:
            print("Unexpected requests:", unexpected, "Handler errors:", handler_errors)
        await browser.call("Page.navigate", {"url": "about:blank"})
        await browser.call("Fetch.disable")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
