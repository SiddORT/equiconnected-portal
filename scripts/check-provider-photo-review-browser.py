"""Browser-only provider photo review fixture; never changes persisted application data."""
import asyncio
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import websockets


PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"
    )
).decode()
PROVIDER_NAME = "Meadow Equine Clinic"
BROKEN_ALT = "A damaged fixture preview with important alt text"
BROKEN_CAPTION = "Treatment room with a damaged preview"


def photo(reference, alt, caption, order, thumbnail=False):
    return {
        "storage_reference": reference,
        "alt_text": alt,
        "caption": caption,
        "display_order": order,
        "is_thumbnail": thumbnail,
    }


def profile(name, photos):
    return {
        "name": name,
        "description": "Equine medicine and rehabilitation.",
        "email": "clinic@example.test",
        "phone": None,
        "website": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "specialization_ids": [],
        "locations": [],
        "phones": [],
        "emails": [],
        "photos": photos,
        "professional_title": None,
        "biography": None,
        "years_experience": None,
        "experience_description": None,
        "qualifications": [],
    }


def make_update(update_id, name, status, current_photos, proposed_photos):
    current_name = f"{PROVIDER_NAME} {name}"
    return {
        "id": update_id,
        "provider_id": f"browser-listing-{update_id}",
        "provider_name": current_name,
        "provider_type": "CLINIC",
        "review_status": status,
        "current_profile": profile(current_name, current_photos),
        "proposed_profile": profile(f"{current_name} updated", proposed_photos),
        "submitted_at": "2026-10-01T05:00:00Z",
        "reviewed_by_user_id": None,
        "reviewed_by_name": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "created_at": "2026-10-01T05:00:00Z",
    }


def rectangle(element):
    rect = element.getBoundingClientRect()
    return {
        "left": rect.left,
        "right": rect.right,
        "top": rect.top,
        "bottom": rect.bottom,
    }


async def main():
    listing_root = "/uploads/providers/browser-listing/photos/"
    retained = photo(
        listing_root + "retained.png",
        "Approved exterior with the former description",
        "Former listing cover",
        0,
        True,
    )
    removed = photo(
        listing_root + "removed.png",
        "Photo proposed for removal",
        "Old waiting area",
        1,
    )
    current_reject = photo(
        listing_root + "reject-current.png",
        "Existing approved consultation room",
        "Approved consultation room",
        0,
        True,
    )
    proposed_photos = [
        photo(
            listing_root + "new.png",
            "Newly uploaded treatment room",
            "Recently added treatment room",
            0,
            True,
        ),
        photo(
            listing_root + "retained.png",
            "Updated accessible text describing the shaded riding arena",
            "Updated arena title",
            1,
        ),
        photo(listing_root + "broken.png", BROKEN_ALT, BROKEN_CAPTION, 2),
    ]
    updates = [
        make_update("browser-photo-approve", "Review approval fixture", "PENDING_REVIEW", [retained, removed], proposed_photos),
        make_update("browser-photo-reject", "Review rejection fixture", "PENDING_REVIEW", [current_reject], proposed_photos),
    ]
    by_id = {item["id"]: item for item in updates}
    image_responses = []

    targets = json.load(urlopen("http://127.0.0.1:9223/json"))
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

        async def fulfill(request_id, body, content_type="application/json", status=200):
            await command(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": status,
                    "responseHeaders": [{"name": "Content-Type", "value": content_type}],
                    "body": base64.b64encode(body).decode(),
                },
            )

        async def intercept(params):
            request = params["request"]
            url = request["url"]
            path = urlparse(url).path
            if path.startswith(listing_root):
                if path.endswith("broken.png"):
                    image_responses.append((path, 404))
                    await fulfill(params["requestId"], b"Fixture image intentionally unavailable", "text/plain", 404)
                else:
                    image_responses.append((path, 200))
                    await fulfill(params["requestId"], base64.b64decode(PNG), "image/png")
                return
            if "/auth/refresh" in path:
                data = {
                    "access_token": "browser-only-photo-review-fixture",
                    "user": {
                        "id": "browser-admin",
                        "email": "reviewer@example.test",
                        "full_name": "Browser reviewer",
                        "first_name": "Browser",
                        "last_name": "Reviewer",
                        "role": "admin",
                        "roles": ["admin"],
                        "is_active": True,
                        "email_verified_at": "2026-10-01T05:00:00Z",
                    },
                }
            elif "/system-settings" in path:
                data = {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
            elif path.rstrip("/") == "/api/v1/admin/provider-profile-updates":
                data = {
                    "data": updates,
                    "meta": {"page": 1, "page_size": 100, "total": len(updates), "total_pages": 1},
                }
            elif "/admin/provider-profile-updates/" in path:
                parts = path.rstrip("/").split("/")
                update_id = parts[-2]
                action = parts[-1]
                update = by_id[update_id]
                if action in ("approve", "reject"):
                    update["review_status"] = "APPROVED" if action == "approve" else "REJECTED"
                    update["reviewed_by_user_id"] = "browser-admin"
                    update["reviewed_by_name"] = "Browser reviewer"
                    update["reviewed_at"] = "2026-10-01T06:00:00Z"
                    update["rejection_reason"] = (
                        None if action == "approve" else "Please replace the unavailable photo preview."
                    )
                data = update
            else:
                await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                return
            await fulfill(params["requestId"], json.dumps(data).encode())

        async def receive():
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    future = pending.pop(message["id"], None)
                    if future:
                        future.set_result(message)
                elif message.get("method") == "Fetch.requestPaused":
                    asyncio.create_task(intercept(message["params"]))

        reader = asyncio.create_task(receive())

        async def evaluate(expression):
            result = await command(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            return result["result"].get("value")

        async def wait_for(expression, description, timeout=15):
            for _ in range(timeout * 10):
                value = await evaluate(expression)
                if value:
                    return value
                await asyncio.sleep(0.1)
            raise AssertionError(f"Timed out waiting for {description}: {await evaluate('document.body.innerText')}")

        async def click_text(text):
            expression = (
                "(() => { const b=[...document.querySelectorAll('button')].find("
                f"b=>b.textContent.trim()==={json.dumps(text)}); if(!b)return false; b.click(); return true; }})()"
            )
            assert await evaluate(expression), f"Button not found: {text}"
            await asyncio.sleep(0.25)

        async def click_last_dialog_button(text):
            expression = (
                "(() => { const d=[...document.querySelectorAll('[role=dialog]')].at(-1); "
                "if(!d)return false; const b=[...d.querySelectorAll('button')].find("
                f"b=>b.textContent.trim()==={json.dumps(text)}); if(!b)return false; b.click(); return true; }})()"
            )
            assert await evaluate(expression), f"Dialog button not found: {text}"
            await asyncio.sleep(0.25)

        async def open_update(update_name):
            action_label = f"Actions for {update_name} update"
            await wait_for(
                f"!!document.querySelector('[aria-label={json.dumps(action_label)}]')",
                f"row action menu for {update_name}",
            )
            await evaluate(f"document.querySelector('[aria-label={json.dumps(action_label)}]').click()")
            await click_text("Compare profiles")
            await wait_for(
                "!!document.querySelector('[role=dialog]')",
                f"comparison dialog for {update_name}",
            )

        async def press_escape():
            await command(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            )
            await command(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            )

        await command("Page.enable")
        await command(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": "*/api/v1/*"},
                    {"urlPattern": "*/uploads/providers/browser-listing/photos/*"},
                ]
            },
        )
        await command(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        domain = os.environ.get("REPLIT_DEV_DOMAIN")
        if not domain:
            raise RuntimeError("Set REPLIT_DEV_DOMAIN to the already-running app host.")
        await command("Page.navigate", {"url": f"https://{domain}/admin/provider-applications?tab=updates"})
        await wait_for(
            f"!!document.querySelector('[aria-label=\"Actions for {PROVIDER_NAME} Review approval fixture update\"]')",
            "provider update list",
        )

        approval_name = f"{PROVIDER_NAME} Review approval fixture"
        await open_update(approval_name)
        photo_details = await evaluate(
            "(() => {const d=document.querySelector('[role=dialog]');"
            "const section=d.querySelector('[aria-label=\"Photo comparison\"]');"
            "const current=section?.querySelector('[aria-label=\"Current photos\"]');"
            "const proposed=section?.querySelector('[aria-label=\"Proposed photos\"]');"
            "const texts=[...section.querySelectorAll('*')].map(e=>e.textContent.trim());"
            "return {current:[...current.querySelectorAll('img')].map(i=>i.alt),"
            "proposed:[...proposed.querySelectorAll('img')].map(i=>i.alt),text:section.innerText}})()"
        )
        assert photo_details["current"] == [
            retained["alt_text"],
            removed["alt_text"],
        ], f"Current photo order, retention, or removal is incorrect: {photo_details}"
        assert photo_details["proposed"] == [item["alt_text"] for item in proposed_photos[:2]], \
            f"Proposed photo additions and order are incorrect: {photo_details}"
        assert BROKEN_ALT in photo_details["text"], \
            f"The broken preview's alt text should remain available: {photo_details}"
        assert BROKEN_CAPTION in photo_details["text"], \
            f"The broken preview's caption should remain available: {photo_details}"
        for status in ("Added", "Removed", "Metadata changed", "Order changed", "Profile photo changed"):
            assert status in photo_details["text"], f"Expected photo change status {status!r}: {photo_details}"
        assert "Profile photo" in photo_details["text"], \
            "The new proposed thumbnail selection should be visible to reviewers."
        assert await evaluate(
            "(() => { const d=document.querySelector('[role=dialog]'); "
            "const card=[...d.querySelectorAll('article')].find(e=>e.innerText.includes("
            f"{json.dumps(BROKEN_CAPTION)})); return Boolean(card && /image could not be loaded|unavailable|failed/i.test(card.innerText)) }})()"
        ), "The broken fixture image needs a clear unavailable-image state."
        await evaluate(
            "for(const img of document.querySelectorAll('[role=dialog] img')) img.scrollIntoView({block:'nearest'})"
        )
        image_state = await wait_for(
            "(() => {const images=[...document.querySelectorAll('[role=dialog] img')]; "
            "return images.length>=4 && images.every(i=>i.complete) ? images.map(i=>({alt:i.alt,naturalWidth:i.naturalWidth,src:i.currentSrc})) : false})()",
            "all successfully loaded photo previews",
        )
        assert all(item["naturalWidth"] > 0 for item in image_state), \
            f"Every image rendered by the comparison should be a successful preview: {image_state}"
        assert all(item["src"].startswith(f"https://{domain}{listing_root}") for item in image_state), image_state
        assert (listing_root + "broken.png", 404) in image_responses, \
            f"The deliberately broken image must receive an actual 404: {image_responses}"
        assert all(
            (urlparse(item["src"]).path, 200) in image_responses for item in image_state
        ), f"Every successful preview should use a successful fixture response: {image_responses}"
        print("Photo preview fixture:", json.dumps(image_state))
        print("Image fixture responses:", json.dumps(image_responses))

        layout_errors = []
        for width, height, mobile, label in (
            (1440, 900, False, "desktop"),
            (375, 812, True, "mobile"),
            (320, 700, True, "mobile-320"),
        ):
            await command(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile},
            )
            await asyncio.sleep(0.25)
            metrics = await evaluate("""(() => {
                const dialog=document.querySelector('[role=dialog]');
                const panel=dialog.firstElementChild;
                const footer=panel.querySelector('footer');
                const header=panel.querySelector('header');
                const scrollable=[...panel.querySelectorAll('*')].find(e =>
                    e.scrollHeight>e.clientHeight+2 && ['auto','scroll'].includes(getComputedStyle(e).overflowY));
                const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
                return {panel:rect(panel),footer:rect(footer),header:rect(header),
                    viewport:{width:window.innerWidth,height:window.innerHeight},
                    devicePixelRatio:window.devicePixelRatio,
                    visualViewport:{width:window.visualViewport?.width,height:window.visualViewport?.height,scale:window.visualViewport?.scale},
                    panelOverflow:panel.scrollWidth>panel.clientWidth,
                    bodyHeight:scrollable?.clientHeight||0,bodyScroll:scrollable?.scrollHeight||0,
                    buttons:[...footer.querySelectorAll('button')].map(b=>({text:b.innerText,...rect(b)}))};
            })()""")
            scale = (
                metrics["devicePixelRatio"] * metrics["visualViewport"]["scale"]
                if metrics else 1
            )
            if not metrics or metrics["panel"]["left"] * scale < 0 or metrics["panel"]["right"] * scale > width:
                layout_errors.append(f"{label}: dialog panel exceeds the {width}px viewport: {metrics}")
            if not metrics or metrics["footer"]["bottom"] * scale > height or metrics["header"]["top"] * scale < 0:
                layout_errors.append(f"{label}: dialog header/footer is outside the {height}px viewport: {metrics}")
            if not metrics or metrics["panelOverflow"]:
                layout_errors.append(f"{label}: dialog panel has horizontal overflow: {metrics}")
            if not metrics or not (metrics["bodyScroll"] > metrics["bodyHeight"] > 0):
                layout_errors.append(f"{label}: dialog comparison content is not internally scrollable: {metrics}")
            if metrics and not all(
                button["bottom"] * scale <= height
                and button["left"] * scale >= 0
                and button["right"] * scale <= width
                for button in metrics["buttons"]
            ):
                layout_errors.append(f"{label}: a footer action is unreachable in the viewport: {metrics}")
            print(f"{label} comparison layout:", json.dumps(metrics))
            await evaluate("""(() => {
                const panel=document.querySelector('[role=dialog]').firstElementChild;
                const scroller=[...panel.querySelectorAll('*')].find(e =>
                    e.scrollHeight>e.clientHeight+2 && ['auto','scroll'].includes(getComputedStyle(e).overflowY));
                if(scroller)scroller.scrollTop=0;
            })()""")
            screenshot = await command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            screenshot_dir = Path("screenshots")
            screenshot_dir.mkdir(exist_ok=True)
            screenshot_path = screenshot_dir / f"provider-photo-review-{label}.png"
            screenshot_path.write_bytes(base64.b64decode(screenshot["data"]))
            print(f"Saved screenshot: {screenshot_path}")
            scroll_result = await evaluate("""(() => {
                const d=document.querySelector('[role=dialog]'), panel=d.firstElementChild, footer=panel.querySelector('footer');
                const scroller=[...panel.querySelectorAll('*')].find(e =>
                    e.scrollHeight>e.clientHeight+2 && ['auto','scroll'].includes(getComputedStyle(e).overflowY));
                if(!scroller)return false;
                scroller.scrollTop=scroller.scrollHeight;
                const f=footer.getBoundingClientRect();
                const viewportHeight=window.innerHeight;
                return {scrollTop:scroller.scrollTop,scrollHeight:scroller.scrollHeight,
                    footerReachable:f.top>=0&&f.bottom<=viewportHeight,
                    panelOverflow:panel.scrollWidth>panel.clientWidth};
            })()""")
            if not scroll_result or scroll_result["scrollTop"] <= 0:
                layout_errors.append(f"{label}: review content did not scroll internally: {scroll_result}")
            if not scroll_result or not scroll_result["footerReachable"] or scroll_result["panelOverflow"]:
                layout_errors.append(f"{label}: footer is unreachable after scrolling: {scroll_result}")
            print(f"{label} scrolled review footer:", json.dumps(scroll_result))

        await click_text("Approve update")
        await wait_for(
            "document.querySelectorAll('[role=dialog]').length>=2",
            "approval confirmation to open",
        )
        await press_escape()
        await asyncio.sleep(0.25)
        assert await evaluate("document.querySelectorAll('[role=dialog]').length===1"), \
            "Escape should close only the decision confirmation."
        assert by_id["browser-photo-approve"]["review_status"] == "PENDING_REVIEW", \
            "Canceling confirmation must not make an API decision."

        await click_text("Approve update")
        await wait_for(
            "document.querySelectorAll('[role=dialog]').length>=2",
            "approval confirmation to reopen",
        )
        await click_last_dialog_button("Approve update")
        await wait_for(
            "document.querySelector('[role=dialog]')?.innerText.toLowerCase().includes('approved')",
            "approved review status to return to the dialog",
        )
        assert await evaluate(
            "document.querySelector('[role=dialog]').innerText.includes('Current approved')"
        ), "The refreshed approval dialog should retain the comparison."
        await click_text("Close")
        print("Approval decision returned APPROVED and refreshed the comparison.")

        rejection_name = f"{PROVIDER_NAME} Review rejection fixture"
        await open_update(rejection_name)
        await click_text("Reject update")
        await wait_for(
            "document.querySelectorAll('[role=dialog]').length>=2",
            "rejection confirmation to open",
        )
        await press_escape()
        await asyncio.sleep(0.25)
        assert await evaluate("document.querySelectorAll('[role=dialog]').length===1"), \
            "Escape should close only the rejection confirmation."
        assert by_id["browser-photo-reject"]["review_status"] == "PENDING_REVIEW", \
            "Canceling rejection must not make an API decision."

        await click_text("Reject update")
        await wait_for(
            "document.querySelectorAll('[role=dialog]').length>=2",
            "rejection confirmation to reopen",
        )
        textarea = await evaluate(
            "(() => {const d=[...document.querySelectorAll('[role=dialog]')].at(-1); "
            "return !!d.querySelector('textarea')})()"
        )
        if textarea:
            await evaluate(
                "(() => {const d=[...document.querySelectorAll('[role=dialog]')].at(-1);"
                "const t=d.querySelector('textarea'); t.value='Please replace the unavailable photo preview.';"
                "t.dispatchEvent(new Event('input',{bubbles:true}));"
                "t.dispatchEvent(new Event('change',{bubbles:true})); return true})()"
            )
        await click_last_dialog_button("Reject update")
        await wait_for(
            "document.querySelector('[role=dialog]')?.innerText.toLowerCase().includes('rejected')",
            "rejected review status to return to the dialog",
        )
        assert await evaluate(
            "document.querySelector('[role=dialog]').innerText.includes('Please replace the unavailable photo preview.')"
        ), "The refreshed rejection dialog should show the returned review reason."
        print("Rejection decision returned REJECTED and refreshed the comparison.")
        print("Browser checks passed: image metadata, successful and failed previews, responsive scrolling, Escape, approval, and rejection.")
        if layout_errors:
            raise AssertionError("Responsive provider photo review layout failure(s):\n" + "\n".join(layout_errors))
        reader.cancel()


asyncio.run(main())