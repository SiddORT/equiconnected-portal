"""Browser-only provider visit scheduling fixture; never changes persisted application data."""
import asyncio
import base64
import copy
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import websockets


PROVIDER_NAME = "Meadow Equine Clinic"
TIME_ZONE = "America/Los_Angeles"


def calendar_date(offset):
    return (datetime.now(ZoneInfo(TIME_ZONE)).date() + timedelta(days=offset)).isoformat()


def make_visit(visit_id, start_date, end_date, city, address):
    return {
        "id": visit_id,
        "start_date": start_date,
        "end_date": end_date,
        "location": {
            "name": f"{city} veterinary event",
            "address_line_1": address,
            "address_line_2": None,
            "city": city,
            "state_province": "California",
            "country": "United States",
            "postal_code": "90210",
            "latitude": None,
            "longitude": None,
            "is_primary": False,
        },
    }


def portal_profile(recorded_visits, additions, pending=True):
    profile_name = f"{PROVIDER_NAME} — Visiting schedule fixture"
    editable = {
        "name": profile_name,
        "description": "Equine medicine and rehabilitation.",
        "email": "clinic@example.test",
        "phone": None,
        "website": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "maximum_working_radius_km": None,
        "emergency_services_available": False,
        "emergency_contact_number": None,
        "specialization_ids": [],
        "professional_title": "Equine veterinarian",
        "biography": "Browser verification fixture.",
        "years_experience": 12,
        "experience_description": "Visiting equine care.",
        "locations": [],
        "phones": [],
        "emails": [],
        "photos": [],
        "qualifications": [],
        "visit_additions": copy.deepcopy(additions),
    }
    return {
        "id": "browser-visiting-provider",
        "name": profile_name,
        "description": "Equine medicine and rehabilitation.",
        "email": "clinic@example.test",
        "phone": None,
        "website": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "maximum_working_radius_km": None,
        "emergency_services_available": False,
        "emergency_contact_number": None,
        "specializations": [],
        "locations": [],
        "photos": [],
        "phones": [],
        "emails": [],
        "doctor_profile": None,
        "doctor_fields_available": True,
        "doctor_availability": "VISITING",
        "can_schedule_visits": True,
        "doctor_visits": copy.deepcopy(recorded_visits),
        "qualifications": [],
        "average_rating": None,
        "review_count": 0,
        "visible_reviews": [],
        "editable_profile": editable,
        "profile_update": {
            "id": "browser-visiting-update",
            "review_status": "PENDING_REVIEW" if pending else "APPROVED",
            "submitted_at": "2026-10-01T05:00:00Z",
            "reviewed_at": None,
            "reviewed_by_name": None,
            "rejection_reason": None,
        } if pending else None,
    }


def update_snapshot(profile):
    source = profile["editable_profile"]
    snapshot = {
        key: copy.deepcopy(source.get(key))
        for key in (
            "name",
            "description",
            "email",
            "phone",
            "website",
            "visit_stability",
            "maximum_working_radius_km",
            "emergency_services_available",
            "emergency_contact_number",
            "specialization_ids",
            "professional_title",
            "biography",
            "years_experience",
            "experience_description",
            "locations",
            "phones",
            "emails",
            "photos",
            "qualifications",
            "visit_additions",
        )
    }
    return snapshot


def admin_update(profile):
    current = {
        "name": profile["name"],
        "description": profile["description"],
        "email": profile["email"],
        "phone": profile["phone"],
        "website": profile["website"],
        "visit_stability": profile["visit_stability"],
        "maximum_working_radius_km": None,
        "emergency_services_available": False,
        "emergency_contact_number": None,
        "specialization_ids": [],
        "professional_title": "Equine veterinarian",
        "biography": "Browser verification fixture.",
        "years_experience": 12,
        "experience_description": "Visiting equine care.",
        "locations": [],
        "phones": [],
        "emails": [],
        "photos": [],
        "qualifications": [],
    }
    return {
        "id": "browser-visiting-update",
        "provider_id": profile["id"],
        "provider_name": profile["name"],
        "provider_type": "DOCTOR",
        "review_status": profile["profile_update"]["review_status"],
        "current_profile": current,
        "proposed_profile": update_snapshot(profile),
        "submitted_at": "2026-10-01T05:00:00Z",
        "reviewed_by_user_id": None,
        "reviewed_by_name": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "created_at": "2026-10-01T05:00:00Z",
    }


async def main():
    today = datetime.now(ZoneInfo(TIME_ZONE)).date()
    visits = [
        make_visit(
            "browser-previous",
            (today - timedelta(days=9)).isoformat(),
            (today - timedelta(days=8)).isoformat(),
            "Previous City",
            "10 History Road",
        ),
        make_visit(
            "browser-current",
            (today - timedelta(days=1)).isoformat(),
            (today + timedelta(days=1)).isoformat(),
            "Current City",
            "20 History Road",
        ),
        make_visit(
            "browser-upcoming",
            (today + timedelta(days=20)).isoformat(),
            (today + timedelta(days=21)).isoformat(),
            "Upcoming City",
            "30 History Road",
        ),
    ]
    draft_visit = {
        "start_date": (today + timedelta(days=35)).isoformat(),
        "end_date": (today + timedelta(days=36)).isoformat(),
        "location": {
            "name": "Draft rodeo",
            "address_line_1": "40 Draft Road",
            "address_line_2": None,
            "city": "Draft City",
            "state_province": "California",
            "country": "United States",
            "postal_code": "90001",
        },
    }
    stored_profile = portal_profile(visits, [draft_visit])
    recorded_visits_before = copy.deepcopy(stored_profile["doctor_visits"])
    patch_requests = []
    profile_reads = 0
    mock_role = "provider"

    targets = json.load(urlopen("http://127.0.0.1:9224/json"))
    target = next(item for item in targets if item.get("type") == "page")
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=10_000_000) as ws:
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
            await command(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": status,
                    "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                    "body": base64.b64encode(json.dumps(body).encode()).decode(),
                },
            )

        async def intercept(params):
            nonlocal profile_reads, stored_profile
            request = params["request"]
            path = urlparse(request["url"]).path
            method = request["method"].upper()
            if path.endswith("/auth/refresh"):
                if mock_role == "admin":
                    role = "admin"
                    user_id = "browser-visits-admin"
                    email = "reviewer@example.test"
                    first_name, last_name = "Browser", "Reviewer"
                else:
                    role = "provider"
                    user_id = "browser-visits-provider-user"
                    email = "clinic@example.test"
                    first_name, last_name = "Meadow", "Veterinarian"
                response = {
                    "access_token": "browser-only-provider-visits-fixture",
                    "user": {
                        "id": user_id,
                        "email": email,
                        "full_name": f"{first_name} {last_name}",
                        "first_name": first_name,
                        "last_name": last_name,
                        "role": role,
                        "roles": [role],
                        "is_active": True,
                        "email_verified_at": "2026-10-01T05:00:00Z",
                    },
                }
            elif path.endswith("/system-settings"):
                response = {
                    "timezone": TIME_ZONE,
                    "date_format": "month_day_year",
                    "time_format": "12_hour",
                }
            elif path.endswith("/provider/portal/specializations") and method == "GET":
                response = []
            elif path.endswith("/provider/portal/profile") and method == "GET":
                profile_reads += 1
                response = copy.deepcopy(stored_profile)
            elif path.endswith("/provider/portal/profile") and method == "PATCH":
                body = json.loads(request.get("postData") or "{}")
                patch_requests.append(copy.deepcopy(body))
                stored_profile["editable_profile"].update({
                    key: copy.deepcopy(value)
                    for key, value in body.items()
                    if key != "visit_additions"
                })
                stored_profile["editable_profile"]["visit_additions"] = copy.deepcopy(
                    body.get("visit_additions", [])
                )
                stored_profile["profile_update"] = {
                    "id": "browser-visiting-update",
                    "review_status": "PENDING_REVIEW",
                    "submitted_at": "2026-10-01T05:00:00Z",
                    "reviewed_at": None,
                    "reviewed_by_name": None,
                    "rejection_reason": None,
                }
                response = copy.deepcopy(stored_profile)
            elif path.rstrip("/") == "/api/v1/admin/provider-profile-updates" and method == "GET":
                update = admin_update(stored_profile)
                response = {
                    "data": [update],
                    "meta": {"page": 1, "page_size": 100, "total": 1, "total_pages": 1},
                }
            else:
                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            await fulfill(params["requestId"], response)

        async def handle_intercept(params):
            try:
                await intercept(params)
            except Exception as exc:
                print(
                    f"API fixture interception failed for {params.get('request', {}).get('url')}: "
                    f"{type(exc).__name__}: {exc}"
                )

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    future = pending.pop(message["id"], None)
                    if future:
                        future.set_result(message)
                elif message.get("method") == "Fetch.requestPaused":
                    asyncio.create_task(handle_intercept(message["params"]))

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result["result"].get("value")

        async def wait_for(expression, description, timeout=20):
            for _ in range(timeout * 10):
                value = await evaluate(expression)
                if value:
                    return value
                await asyncio.sleep(0.1)
            raise AssertionError(
                f"Timed out waiting for {description}: {await evaluate('document.body.innerText')}"
            )

        reload_number = 0

        async def reload_provider(description):
            nonlocal reload_number
            reads_before_reload = profile_reads
            reload_number += 1
            await command(
                "Page.navigate",
                {
                    "url": (
                        f"https://{domain}/provider/account"
                        f"?browser-verification-reload={reload_number}"
                    )
                },
            )
            await wait_for(
                "!document.body.innerText.includes('Verifying session')",
                f"{description} session restoration",
                timeout=30,
            )
            await wait_for(
                "!!document.querySelector('[aria-label=\"Provider profile sections\"] "
                "[role=tab][id=\"provider-tab-visits\"]')",
                description,
            )
            assert profile_reads > reads_before_reload, \
                f"{description} did not request the persisted provider profile."

        async def click_button(text):
            expression = (
                "(() => { const b=[...document.querySelectorAll('button')].find("
                f"b=>b.textContent.trim()==={json.dumps(text)}||b.getAttribute('aria-label')==={json.dumps(text)}); "
                "if(!b)return false; b.click(); return true; })()"
            )
            assert await evaluate(expression), f"Button not found: {text}"
            await asyncio.sleep(0.3)

        async def set_labeled_input(label, value):
            expression = (
                "(() => { const label=[...document.querySelectorAll('label')].find("
                f"e=>e.textContent.trim()==={json.dumps(label)}); "
                "if(!label)return false; const input=label.control||label.querySelector('input,textarea'); "
                "if(!input)return false; const setter=Object.getOwnPropertyDescriptor("
                "Object.getPrototypeOf(input),'value')?.set; "
                f"if(setter)setter.call(input,{json.dumps(value)});else input.value={json.dumps(value)}; "
                "input.dispatchEvent(new Event('input',{bubbles:true})); "
                "input.dispatchEvent(new Event('change',{bubbles:true})); return true; })()"
            )
            assert await evaluate(expression), f"Input label not found: {label}"

        async def input_value(label):
            return await evaluate(
                "(() => { const label=[...document.querySelectorAll('label')].find("
                f"e=>e.textContent.trim()==={json.dumps(label)}); "
                "return label?.control?.value ?? label?.querySelector('input,textarea')?.value ?? null; })()"
            )

        async def press_key(key, code, virtual_key):
            await command(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": key, "code": code, "windowsVirtualKeyCode": virtual_key},
            )
            await command(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": key, "code": code, "windowsVirtualKeyCode": virtual_key},
            )

        async def save_screenshot(name):
            result = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            directory = Path("screenshots")
            directory.mkdir(exist_ok=True)
            path = directory / name
            path.write_bytes(base64.b64decode(result["data"]))
            print(f"Saved screenshot: {path}")

        try:
            await command("Page.enable")
            await command(
                "Fetch.enable",
                {"patterns": [{"urlPattern": "*/api/v1/*"}]},
            )
            await command(
                "Emulation.setTimezoneOverride",
                {"timezoneId": TIME_ZONE},
            )
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
            )
            domain = os.environ.get("REPLIT_DEV_DOMAIN")
            if not domain:
                raise RuntimeError("Set REPLIT_DEV_DOMAIN to the already-running app host.")
            await command("Page.navigate", {"url": f"https://{domain}/provider/account"})
            await wait_for(
                "!!document.querySelector('[aria-label=\"Provider profile sections\"]') "
                "&& !!document.querySelector('[aria-label=\"Provider profile sections\"] [role=tab][aria-selected=true]')",
                "provider portal and profile",
            )
            await wait_for(
                f"!!document.querySelector('[aria-label=\"Provider profile sections\"] [role=tab][id=\"provider-tab-visits\"]')",
                "Visits tab capability",
            )
            assert profile_reads >= 1, f"Expected an initial profile read, got {profile_reads}"

            # Visit history uses a real browser timezone, while the date-only schedule remains a calendar date.
            await evaluate("document.querySelector('#provider-tab-basic').focus()")
            for _ in range(5):
                await press_key("ArrowRight", "ArrowRight", 39)
            keyboard_state = await evaluate(
                "(() => ({selected:document.querySelector('[role=tab][aria-selected=true]')?.textContent.trim(),"
                "patchCount:document.querySelector('form')?.dataset.patchCount||'0',"
                "visible:document.querySelector('#provider-panel-visits')?.hidden===false}))()"
            )
            assert keyboard_state["selected"] == "Visits" and keyboard_state["visible"], keyboard_state
            assert not patch_requests, "Keyboard tab navigation unexpectedly submitted the profile."
            await asyncio.sleep(0.2)

            history = await evaluate("""(() => {
                const section=document.querySelector('[aria-labelledby="visit-history-heading"]');
                const periods=[...section.querySelectorAll(':scope > section')].map(p=>({
                    label:p.querySelector('h5')?.textContent.trim(),
                    dates:[...p.querySelectorAll('time')].map(t=>t.dateTime),
                    text:p.innerText
                }));
                return {periods,interactive:section.querySelectorAll('input,button,select,textarea,a').length,
                today:(()=>{const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',
                    year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
                    const v=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${v.year}-${v.month}-${v.day}`})()};
            })()""")
            assert [item["label"] for item in history["periods"]] == ["Previous", "Current", "Upcoming"], history
            assert history["periods"][0]["dates"] == [
                visits[0]["start_date"], visits[0]["end_date"]
            ], history
            assert history["periods"][1]["dates"] == [
                visits[1]["start_date"], visits[1]["end_date"]
            ], history
            assert history["periods"][2]["dates"] == [
                visits[2]["start_date"], visits[2]["end_date"]
            ], history
            assert history["interactive"] == 0, f"Recorded history is not read-only: {history}"
            assert history["today"] == today.isoformat(), history
            assert history["periods"][1]["dates"][0] == calendar_date(-1)
            print("Provider recorded visit groups (read-only):", json.dumps(history))

            await save_screenshot("provider-visits-desktop.png")
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
            )
            mobile_layout = await evaluate("""(() => ({
                viewport:window.innerWidth,
                documentWidth:document.documentElement.scrollWidth,
                bodyWidth:document.body.scrollWidth,
                visitsVisible:document.querySelector('#provider-panel-visits')?.hidden===false,
                tabRect:(()=>{const r=document.querySelector('#provider-tab-visits').getBoundingClientRect();return {left:r.left,right:r.right}})()
            }))()""")
            assert mobile_layout["viewport"] == 390, mobile_layout
            assert mobile_layout["documentWidth"] <= 390 and mobile_layout["bodyWidth"] <= 390, mobile_layout
            assert mobile_layout["visitsVisible"], mobile_layout
            await save_screenshot("provider-visits-mobile-390.png")
            await evaluate(
                "document.querySelector('#visit-history-heading').scrollIntoView({block:'start'})"
            )
            await asyncio.sleep(0.2)
            await save_screenshot("provider-visits-mobile-390-scrolled.png")
            print("Mobile 390px Visits layout:", json.dumps(mobile_layout))
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
            )

            # Revise the existing draft in-place; merely editing/navigating does not submit it.
            await set_labeled_input("Visit 1 city", "Revised Draft City")
            await set_labeled_input("Visit 1 address line 1", "41 Revised Draft Road")
            assert not patch_requests, "Editing a proposed visit submitted it without an explicit save."
            await click_button("Save profile")
            await wait_for(
                "document.body.innerText.includes('Your proposed profile update is awaiting administrator review')",
                "pending-review save confirmation",
            )
            assert len(patch_requests) == 1, f"Expected one explicit PATCH, got {len(patch_requests)}"
            revised = patch_requests[0].get("visit_additions", [])
            assert len(revised) == 1, revised
            assert revised[0]["start_date"] == draft_visit["start_date"]
            assert revised[0]["end_date"] == draft_visit["end_date"]
            assert revised[0]["location"]["city"] == "Revised Draft City", revised
            assert revised[0]["location"]["address_line_1"] == "41 Revised Draft Road", revised
            assert stored_profile["doctor_visits"] == recorded_visits_before, \
                "Saving a proposed-visit revision changed the approved visit history."

            reads_before_revision_reload = profile_reads
            await reload_provider("provider portal after revision reload")
            await evaluate("document.querySelector('#provider-tab-visits').click()")
            await wait_for(
                "document.querySelector('#portal-visit-0-city')?.value==='Revised Draft City'",
                "revised visit draft after reload",
            )
            assert profile_reads > reads_before_revision_reload, \
                f"Reload did not read the revised profile: {profile_reads}"
            assert stored_profile["editable_profile"]["visit_additions"][0]["location"]["city"] == "Revised Draft City"
            print("Revised draft persisted across reload; PATCH count:", len(patch_requests))

            # Remove the prior proposal, then add a new independent one-day visit using the form.
            current_history = await evaluate(
                "document.querySelector('[aria-labelledby=\"visit-history-heading\"]').innerText"
            )
            await click_button("Remove proposed visit 1")
            assert await evaluate("!document.querySelector('#portal-visit-0-start-date')"), \
                "Removing the proposed visit did not clear its date fields."
            assert await evaluate(
                "document.querySelector('[aria-labelledby=\"visit-history-heading\"]').innerText"
            ) == current_history, "Removing a proposed visit changed recorded visit history."
            await click_button("Add visit")
            await wait_for(
                "!!document.querySelector('#portal-visit-0-start-date')",
                "new proposed visit form",
            )
            new_day = (today + timedelta(days=15)).isoformat()
            await set_labeled_input("Visit 1 start date", new_day)
            await set_labeled_input("Visit 1 end date", new_day)
            await set_labeled_input("Visit 1 location name", "One-day mobile clinic")
            await set_labeled_input("Visit 1 address line 1", "515 Visiting Vet Lane")
            await set_labeled_input("Visit 1 city", "Los Angeles")
            await set_labeled_input("Visit 1 state, province, or emirate", "California")
            await set_labeled_input("Visit 1 country", "United States")
            await set_labeled_input("Visit 1 postal code", "90012")
            assert not patch_requests or len(patch_requests) == 1, \
                "Proposed visit edits submitted before the user selected Save profile."
            await click_button("Save profile")
            await wait_for(
                "document.body.innerText.includes('Your proposed profile update is awaiting administrator review')",
                "pending review notification after new visit submission",
            )
            assert len(patch_requests) == 2, f"Expected exactly two explicit PATCH saves, got {len(patch_requests)}"
            saved_additions = patch_requests[-1].get("visit_additions", [])
            assert len(saved_additions) == 1, saved_additions
            submitted = saved_additions[0]
            assert submitted["start_date"] == new_day and submitted["end_date"] == new_day, submitted
            assert submitted["location"]["address_line_1"] == "515 Visiting Vet Lane", submitted
            assert submitted["location"]["city"] == "Los Angeles", submitted
            assert stored_profile["doctor_visits"] == recorded_visits_before, \
                "Submitting a new visit changed the existing approved visit history."

            reads_before_final_reload = profile_reads
            await reload_provider("provider portal after final save reload")
            await evaluate("document.querySelector('#provider-tab-visits').click()")
            await wait_for(
                f"document.querySelector('#portal-visit-0-start-date')?.value==={json.dumps(new_day)}",
                "same-day visit draft after reload",
            )
            assert await input_value("Visit 1 end date") == new_day
            assert await input_value("Visit 1 address line 1") == "515 Visiting Vet Lane"
            assert await input_value("Visit 1 city") == "Los Angeles"
            assert len(patch_requests) == 2
            assert profile_reads > reads_before_final_reload, \
                f"Final reload did not read the saved one-day visit: {profile_reads}"
            assert stored_profile["editable_profile"]["visit_additions"] == saved_additions
            assert stored_profile["doctor_visits"] == recorded_visits_before
            print("Added one-day visit persisted after reload; PATCH count:", len(patch_requests))

            # Switch only the intercepted session identity to admin for the real comparison UI.
            mock_role = "admin"
            await command(
                "Page.navigate",
                {"url": f"https://{domain}/admin/provider-applications?tab=updates"},
            )
            row_action_label = f"Actions for {PROVIDER_NAME} — Visiting schedule fixture update"
            await wait_for(
                f"!!document.querySelector('[aria-label={json.dumps(row_action_label)}]')",
                "admin provider profile updates fixture",
            )
            await evaluate(f"document.querySelector('[aria-label={json.dumps(row_action_label)}]').click()")
            await click_button("Compare profiles")
            await wait_for("!!document.querySelector('[role=dialog] table')", "admin profile comparison")
            admin_visit_row = await evaluate("""(() => {
                const row=[...document.querySelectorAll('[role=dialog] table tr')]
                    .find(r=>r.querySelector('th')?.textContent.trim()==='Visit additions');
                return row ? [...row.children].map(cell=>cell.innerText.trim()) : null;
            })()""")
            assert admin_visit_row and len(admin_visit_row) == 3, admin_visit_row
            expected_date = datetime.combine(today + timedelta(days=15), datetime.min.time()).strftime("%b %d, %Y")
            expected_date = expected_date.replace(" 0", " ")
            current_cell, proposed_cell = admin_visit_row[1], admin_visit_row[2]
            assert "Existing visit history is retained." in current_cell, admin_visit_row
            assert f"{expected_date} – {expected_date} (inclusive)" in proposed_cell, admin_visit_row
            for value in (
                "Address line 1:",
                "515 Visiting Vet Lane",
                "City:",
                "Los Angeles",
                "State / province:",
                "California",
                "Country:",
                "United States",
                "Postal code:",
                "90012",
            ):
                assert value in proposed_cell, f"Admin comparison omitted {value!r}: {admin_visit_row}"
            assert "Not provided" in proposed_cell, \
                f"Admin comparison should render absent visit fields explicitly: {admin_visit_row}"
            expected_iso = (today + timedelta(days=15)).isoformat()
            assert expected_iso == new_day, (expected_iso, new_day)
            assert await evaluate(
                "Intl.DateTimeFormat().resolvedOptions().timeZone==='America/Los_Angeles'"
            ), "Browser timezone override was not applied."
            print("Admin proposed visit snapshot:", json.dumps(admin_visit_row))
            print(
                "Browser checks passed: timezone-aware date-only visit history, keyboard navigation, "
                "read-only recorded visits, desktop/mobile layout, draft revision/removal, explicit saves, "
                "reload persistence, and admin inclusive-date snapshot."
            )
        finally:
            reader.cancel()


asyncio.run(main())