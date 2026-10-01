"""Real browser/API smoke for private messaging in an owned PostgreSQL schema.

Prerequisites: the real frontend is already running at http://127.0.0.1:5000,
PostgreSQL settings and the protected messaging keyring are available through
the normal application configuration, and Chromium is installed.

Run from the repository root:

    python3 scripts/check-private-messaging-isolated-browser.py

The harness creates only a randomly named ``pm_smoke_*`` schema, starts its
own API processes on ports 8008 and 8009, launches disposable Chromium
profiles, intercepts API-looking browser requests and routes only /api/v1
through CDP + an in-memory HTTP client, and drops only its owned schema in
``finally``.
No key values, JWTs, request bodies, or API response bodies are written to
logs or evidence. SMTP methods in the temporary backend are no-op counted.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import UUID

import httpx
import websockets
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
APP_URL = "http://127.0.0.1:5000"
WORKER = ROOT / "scripts" / "private-messaging-smoke-backend.py"
EVIDENCE_DIR = ROOT / "screenshots" / "private-messaging-isolated-smoke"
CAPTURED_SCREENSHOTS: list[Path] = []
SMOKE_PASSWORD = "IsolatedSyntheticSmokeOnly!2026"
# Reserved example.com passes normal EmailStr validation; .test is rejected.
# The worker stubs SMTP before startup, so these can never be delivered.
MEMBER_EMAIL = "synthetic-member@example.com"
PROVIDER_EMAIL = "synthetic-provider@example.com"
STRANGER_EMAIL = "synthetic-stranger@example.com"
LISTING_EMAIL = "synthetic-listing-contact@example.com"
LISTING_PHONE = "+1 555 013 0200"
MEMBER_PHONE = "+1 555 013 0140"
PROVIDER_NAME = "Synthetic Isolated Messaging Clinic"
INITIAL_BODY = "SYNTHETIC-SMOKE: initial message to the isolated provider."
REPLY_BODY = "SYNTHETIC-SMOKE: isolated provider reply."
FAILURE_BODY = "SYNTHETIC-SMOKE: must not persist while encryption is unavailable."

sys.path.insert(0, str(BACKEND))


@dataclass
class Seed:
    schema: str
    provider_id: str
    member_id: str
    provider_user_id: str
    stranger_id: str
    member_email: str = MEMBER_EMAIL
    provider_email: str = PROVIDER_EMAIL
    stranger_email: str = STRANGER_EMAIL


class IsolatedDatabase:
    def __init__(self, database_url: str, schema: str):
        self.database_url = self._normalize_url(database_url)
        self.schema = schema
        self.engine = create_engine(self.database_url, pool_pre_ping=True)
        event.listen(self.engine, "connect", self._pin_schema)

    @staticmethod
    def _normalize_url(database_url: str) -> str:
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    def _pin_schema(self, dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f'SET search_path TO "{self.schema}"')
        cursor.close()
        dbapi_connection.commit()

    def verify_pin(self) -> None:
        with self.engine.connect() as connection:
            actual = connection.execute(text("SELECT current_schema()")).scalar_one()
            if actual != self.schema:
                raise RuntimeError("Isolated database search_path validation failed.")

    def close(self) -> None:
        self.engine.dispose()


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def _assert_frontend_and_prerequisites() -> str:
    from app.core.config import get_settings
    from app.services.messaging_encryption import ensure_encryption_available

    settings = get_settings()
    if settings.ENVIRONMENT != "development" or os.environ.get("REPLIT_DEPLOYMENT") == "1":
        raise RuntimeError("This smoke is restricted to a local development environment.")
    if not settings.DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+")):
        raise RuntimeError("This smoke requires the configured PostgreSQL development database.")
    # Validate the real protected development configuration without inspecting
    # or displaying either the keyring or active key value.
    ensure_encryption_available()

    try:
        response = httpx.get(APP_URL, timeout=4)
    except Exception:
        raise RuntimeError("The already-running frontend is not reachable on port 5000.") from None
    if response.status_code >= 500:
        raise RuntimeError("The already-running frontend returned a server error.")

    if not shutil.which("chromium") and not shutil.which("chromium-browser") and not shutil.which("google-chrome"):
        raise RuntimeError("Chromium is required for this browser smoke.")
    for port in (8008, 8009):
        if not _port_is_free(port):
            raise RuntimeError(f"Required disposable backend port {port} is already occupied.")
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return settings.DATABASE_URL


def _create_schema(database_url: str, schema: str) -> None:
    admin_engine = create_engine(IsolatedDatabase._normalize_url(database_url), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            # Do not use IF NOT EXISTS: ownership is established only by a
            # successful CREATE issued here for this unpredictable name.
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.commit()
    finally:
        admin_engine.dispose()


def _drop_owned_schema(database_url: str, schema: str) -> None:
    if not re.fullmatch(r"pm_smoke_[a-z0-9_]{1,48}", schema):
        raise RuntimeError("Refusing to drop a schema not owned by this smoke.")
    admin_engine = create_engine(IsolatedDatabase._normalize_url(database_url), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            connection.commit()
    finally:
        admin_engine.dispose()


def _seed_schema(database: IsolatedDatabase, schema: str) -> Seed:
    from app.core.security import hash_password
    from app.db.base import Base
    from app.models.enums import (
        ProviderStatus,
        ProviderType,
        PublicationStatus,
        VisitStability,
    )
    from app.models.provider import (
        DirectProviderPortalAccess,
        Provider,
        ProviderEmail,
        ProviderLocation,
        ProviderPhone,
    )
    from app.models.role import Role
    from app.models.user import User, UserRole

    Base.metadata.create_all(bind=database.engine)
    database.verify_pin()

    now = datetime.now(timezone.utc)
    password_hash = hash_password(SMOKE_PASSWORD)
    with Session(database.engine) as session:
        role_rows: dict[str, Role] = {}
        for role_name in ("horse_owner", "provider"):
            role = Role(name=role_name, description=f"Synthetic smoke role: {role_name}")
            session.add(role)
            role_rows[role_name] = role
        session.flush()

        member = User(
            email=MEMBER_EMAIL,
            password_hash=password_hash,
            first_name="Synthetic",
            last_name="Member",
            mobile_number=MEMBER_PHONE,
            email_verified_at=now,
            is_active=True,
            role=role_rows["horse_owner"],
        )
        provider_user = User(
            email=PROVIDER_EMAIL,
            password_hash=password_hash,
            first_name="Synthetic",
            last_name="Provider",
            mobile_number="+1 555 013 0150",
            email_verified_at=now,
            is_active=True,
            role=role_rows["provider"],
        )
        stranger = User(
            email=STRANGER_EMAIL,
            password_hash=password_hash,
            first_name="Synthetic",
            last_name="Stranger",
            mobile_number="+1 555 013 0160",
            email_verified_at=now,
            is_active=True,
            role=role_rows["horse_owner"],
        )
        session.add_all((member, provider_user, stranger))
        session.flush()
        session.add_all(
            UserRole(user_id=account.id, role_id=account.role_id)
            for account in (member, provider_user, stranger)
        )

        provider = Provider(
            provider_type=ProviderType.CLINIC,
            name=PROVIDER_NAME,
            description="Synthetic listing created only in an isolated smoke schema.",
            email=LISTING_EMAIL,
            phone=LISTING_PHONE,
            visit_stability=VisitStability.STABLE_VISIT,
            status=ProviderStatus.ACTIVE,
            publication_status=PublicationStatus.PUBLISHED,
        )
        session.add(provider)
        session.flush()
        session.add_all(
            (
                DirectProviderPortalAccess(
                    provider_id=provider.id,
                    user_id=provider_user.id,
                    recipient_email=PROVIDER_EMAIL,
                    sent_at=now,
                ),
                ProviderLocation(
                    provider_id=provider.id,
                    name="Synthetic test location",
                    address_line_1="1 Synthetic Way",
                    city="Synthetic City",
                    state_province="Test State",
                    country="Test Country",
                    postal_code="00000",
                    is_primary=True,
                ),
                ProviderPhone(
                    provider_id=provider.id,
                    country_code="+1",
                    number="555 013 0200",
                    is_primary=True,
                ),
                ProviderEmail(
                    provider_id=provider.id,
                    email=LISTING_EMAIL,
                    is_primary=True,
                ),
            )
        )
        session.commit()
        seed = Seed(
            schema=schema,
            provider_id=str(provider.id),
            member_id=str(member.id),
            provider_user_id=str(provider_user.id),
            stranger_id=str(stranger.id),
        )
    return seed


class BackendProcess:
    def __init__(self, port: int, schema: str, key_mode: str):
        self.port = port
        self.schema = schema
        self.key_mode = key_mode
        self.process: subprocess.Popen | None = None
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self) -> None:
        env = os.environ.copy()
        previous_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(BACKEND) + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
        # Every backend engine, including its background notification worker,
        # is scoped to the newly created schema. Key settings are inherited
        # unchanged from the protected development configuration.
        env["PGOPTIONS"] = f"-csearch_path={self.schema}"
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(WORKER),
                "--port",
                str(self.port),
                "--schema",
                self.schema,
                "--key-mode",
                self.key_mode,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.process = None
                raise RuntimeError("The isolated backend failed to start.")
            try:
                response = httpx.get(f"{self.base_url}/health", timeout=0.7)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    return
            except Exception:
                pass
            time.sleep(0.2)
        self.stop()
        raise RuntimeError("The isolated backend did not become healthy.")

    def stop(self) -> None:
        process = self.process
        if process is None:
            return
        self.process = None
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def smtp_event_count(self) -> int:
        response = httpx.get(f"{self.base_url}/_smoke/smtp-event-count", timeout=3)
        response.raise_for_status()
        result = response.json()
        return int(result["count"])


class NoCookieAsyncTransport(httpx.AsyncBaseTransport):
    """Pass backend responses to HTTPX without retaining refresh cookies."""

    def __init__(self):
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.inner.handle_async_request(request)
        headers = [
            header
            for header in response.headers.raw
            if header[0].lower() != b"set-cookie"
        ]
        return httpx.Response(
            status_code=response.status_code,
            headers=headers,
            stream=response.stream,
            extensions=response.extensions,
            request=request,
        )

    async def aclose(self) -> None:
        await self.inner.aclose()


def _conversation_storage_check(database: IsolatedDatabase, seed: Seed) -> int:
    from app.models.messaging import ProviderConversation, ProviderMessage

    with Session(database.engine) as session:
        conversation = session.scalar(
            select(ProviderConversation).where(
                ProviderConversation.member_user_id == UUID(seed.member_id),
                ProviderConversation.provider_id == UUID(seed.provider_id),
                ProviderConversation.provider_user_id == UUID(seed.provider_user_id),
            )
        )
        if conversation is None:
            raise AssertionError("Expected synthetic conversation was not persisted.")
        messages = list(
            session.scalars(
                select(ProviderMessage)
                .where(ProviderMessage.conversation_id == conversation.id)
                .order_by(ProviderMessage.sequence)
            ).all()
        )
        if len(messages) != 2:
            raise AssertionError("Expected two encrypted messages in the isolated conversation.")
        if [message.sequence for message in messages] != [1, 2]:
            raise AssertionError("Stored message sequence was not preserved.")
        if not all(message.body_ciphertext.startswith("v1.") for message in messages):
            raise AssertionError("A stored message is not in the encrypted envelope format.")
        if any(
            cleartext in message.body_ciphertext
            for message, cleartext in zip(messages, (INITIAL_BODY, REPLY_BODY))
        ):
            raise AssertionError("Plaintext message content was found in stored ciphertext.")
        if MEMBER_EMAIL in conversation.contact_snapshot_ciphertext:
            raise AssertionError("Member email was found in the stored contact snapshot.")
        if MEMBER_PHONE in conversation.contact_snapshot_ciphertext:
            raise AssertionError("Member phone was found in the stored contact snapshot.")
        if session.scalar(
            select(ProviderConversation.id).where(
                ProviderConversation.member_user_id == UUID(seed.stranger_id)
            )
        ):
            raise AssertionError("The synthetic stranger unexpectedly acquired a conversation.")
        return len(messages)


class BrowserRequestAbandoned(Exception):
    """Chromium cancelled an intercepted request during route navigation."""


class Browser:
    def __init__(self, websocket_url: str, profile_dir: tempfile.TemporaryDirectory):
        self.websocket_url = websocket_url
        self.profile_dir = profile_dir
        self.ws = None
        self.reader: asyncio.Task | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.counter = 0
        self.handlers: list[asyncio.Task] = []
        self.client = httpx.AsyncClient(
            timeout=20,
            follow_redirects=False,
            transport=NoCookieAsyncTransport(),
        )
        self.backend_url = ""
        self.api_request_count = 0
        self.transport_error_count = 0
        self.statuses: Counter[tuple[str, str, int]] = Counter()
        self.force_server_consent_rejection = False
        self.server_consent_rejection_seen = False
        self.stage = "connected"

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.websocket_url, max_size=20_000_000)
        self.reader = asyncio.create_task(self._receive())
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1440,
                "height": 1000,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        await self.call(
            "Fetch.enable",
            {
                "patterns": [
                    # Intercept only same-origin API routes. A broad */api/*
                    # also matches frontend modules such as /src/api/auth.ts.
                    # The handler fails closed for same-origin API paths outside
                    # /api/v1 rather than letting Vite proxy them.
                    {"urlPattern": f"{APP_URL}/api/*", "requestStage": "Request"},
                ]
            },
        )
        self.handlers.append(asyncio.create_task(self._keepalive()))

    async def _keepalive(self) -> None:
        while True:
            await asyncio.sleep(3600)

    async def close(self) -> None:
        for task in self.handlers:
            task.cancel()
        if self.reader is not None:
            self.reader.cancel()
        if self.ws is not None:
            await self.ws.close()
        await self.client.aclose()
        self.profile_dir.cleanup()

    async def _receive(self) -> None:
        async for raw in self.ws:
            message = json.loads(raw)
            if "id" in message:
                future = self.pending.pop(message["id"], None)
                if future is not None and not future.done():
                    future.set_result(message)
            elif message.get("method") == "Fetch.requestPaused":
                task = asyncio.create_task(self._route_api_request(message["params"]))
                self.handlers.append(task)

    async def call(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.counter] = future
        await self.ws.send(
            json.dumps(
                {
                    "id": self.counter,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        result = await asyncio.wait_for(future, timeout=20)
        if "error" in result:
            if method == "Fetch.fulfillRequest" and "Invalid InterceptionId" in result["error"].get("message", ""):
                raise BrowserRequestAbandoned()
            raise RuntimeError(f"Chromium CDP command failed: {method}.")
        return result.get("result", {})

    async def evaluate(self, expression: str) -> Any:
        result = await self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if "exceptionDetails" in result:
            raise RuntimeError("Browser page evaluation failed.")
        return result["result"].get("value")

    async def _route_api_request(self, params: dict) -> None:
        request = params.get("request", {})
        request_id = params.get("requestId")
        parsed = urlsplit(request.get("url", ""))
        path = parsed.path
        method = request.get("method", "GET").upper()
        if not path.startswith("/api/v1/") or not self.backend_url:
            self.transport_error_count += 1
            await self._fulfill_failure(request_id)
            return

        self.api_request_count += 1
        query = f"?{parsed.query}" if parsed.query else ""
        destination = f"{self.backend_url}{path}{query}"
        ignored_request_headers = {
            "host",
            "origin",
            "referer",
            "content-length",
            "connection",
            "accept-encoding",
        }
        headers = {
            name: value
            for name, value in request.get("headers", {}).items()
            if name.lower() not in ignored_request_headers
        }
        body = request.get("postData")
        if (
            path == "/api/v1/messages/start"
            and method == "POST"
            and self.force_server_consent_rejection
            and body is not None
        ):
            try:
                synthetic_request = json.loads(body)
                synthetic_request["consent"] = False
                body = json.dumps(synthetic_request, separators=(",", ":"))
                self.force_server_consent_rejection = False
            except (TypeError, json.JSONDecodeError):
                self.transport_error_count += 1
                await self._fulfill_failure(request_id)
                return
        try:
            upstream = await self.client.request(
                method,
                destination,
                headers=headers,
                content=body.encode("utf-8") if body is not None else None,
            )
            self.statuses[(method, path, upstream.status_code)] += 1
            if (
                path == "/api/v1/messages/start"
                and method == "POST"
                and upstream.status_code == 422
            ):
                self.server_consent_rejection_seen = True
            # Forward only response metadata the frontend needs. In particular,
            # never read or forward Set-Cookie (the refresh JWT); the access
            # token remains only in the app's existing JS memory model.
            response_headers = []
            for name in ("content-type", "cache-control", "retry-after", "www-authenticate"):
                response_headers.extend(
                    {"name": name, "value": value}
                    for value in upstream.headers.get_list(name)
                )
            await self.call(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": upstream.status_code,
                    "responseHeaders": response_headers,
                    "body": base64.b64encode(upstream.content).decode("ascii"),
                },
            )
        except BrowserRequestAbandoned:
            # Navigation/AbortController can cancel a request after its real
            # isolated API response was obtained. No live API fallback occurs.
            return
        except Exception as exc:
            self.transport_error_count += 1
            print(f"SMOKE routing failure type={type(exc).__name__}", flush=True)
            await self._fulfill_failure(request_id)

    async def _fulfill_failure(self, request_id: str) -> None:
        if not request_id:
            return
        payload = b'{"detail":{"message":"Isolated backend routing failed."}}'
        try:
            await self.call(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": 599,
                    "responseHeaders": [
                        {"name": "Content-Type", "value": "application/json"},
                    ],
                    "body": base64.b64encode(payload).decode("ascii"),
                },
            )
        except Exception:
            # Do not emit CDP errors or request contents into logs.
            return

    async def navigate(self, path: str) -> None:
        self.stage = "navigate to login route"
        result = await self.call("Page.navigate", {"url": f"{APP_URL}{path}"})
        if result.get("errorText"):
            await self._report_safe_diagnostics("login route navigation")
            raise RuntimeError("The frontend navigation failed.")
        await self.wait_for(
            f"location.pathname === {json.dumps(path)} && document.readyState !== 'loading'",
            "login route document readiness",
        )

    async def navigate_in_app(self, path: str) -> None:
        expression = (
            "(() => { history.pushState({}, '', "
            f"{json.dumps(path)}); window.dispatchEvent(new PopStateEvent('popstate')); "
            "return true; })()"
        )
        if not await self.evaluate(expression):
            raise AssertionError("Could not navigate within the frontend application.")

    async def wait_for(self, expression: str, description: str, timeout: int = 25) -> None:
        self.stage = description
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            try:
                if await self.evaluate(expression):
                    return
            except Exception:
                pass
            await asyncio.sleep(0.2)
        await self._report_safe_diagnostics(description)
        raise AssertionError(f"Timed out waiting for {description}.")

    @staticmethod
    def _safe_route_path(value: str) -> str:
        path = urlsplit(value).path
        path = re.sub(
            r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)",
            "/<id>",
            path,
        )
        path = re.sub(r"/[^/]{24,}(?=/|$)", "/<segment>", path)
        return path[:180] or "/"

    async def _report_safe_diagnostics(self, stage: str) -> None:
        try:
            route = await self.evaluate("location.pathname")
            safe_route = self._safe_route_path(str(route))
        except Exception:
            safe_route = "<unavailable>"
        safe_statuses = sorted(
            (
                method
                if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
                else "OTHER",
                self._safe_route_path(path),
                status,
                count,
            )
            for (method, path, status), count in self.statuses.items()
        )
        print(
            f"SMOKE-DIAGNOSTIC stage={stage!r} route={safe_route!r} "
            f"api_requests={self.api_request_count} transport_errors={self.transport_error_count} "
            f"statuses={safe_statuses!r}",
            file=sys.stderr,
            flush=True,
        )

    async def wait_for_text(self, value: str, description: str, timeout: int = 25) -> None:
        await self.wait_for(
            f"document.body.innerText.includes({json.dumps(value)})",
            description,
            timeout,
        )

    async def click_text(self, value: str) -> None:
        expression = (
            "(() => { const target = [...document.querySelectorAll('button,a')].find("
            f"element => element.innerText.trim() === {json.dumps(value)}); "
            "if (!target) return false; target.click(); return true; })()"
        )
        if not await self.evaluate(expression):
            raise AssertionError(f"Could not find visible control: {value}.")
        await asyncio.sleep(0.2)

    async def click_conversation(self, path: str) -> None:
        expression = (
            "(() => { const target = [...document.querySelectorAll('a[href]')].find("
            f"element => new URL(element.href).pathname === {json.dumps(path)}); "
            "if (!target) return false; target.click(); return true; })()"
        )
        if not await self.evaluate(expression):
            raise AssertionError("The synthetic conversation was not present in this inbox.")
        await asyncio.sleep(0.2)

    async def set_input(self, selector: str, value: str) -> None:
        expression = (
            "(() => { const input = document.querySelector("
            f"{json.dumps(selector)}); if (!input) return false; "
            "const setter = Object.getOwnPropertyDescriptor("
            "input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : "
            "HTMLInputElement.prototype, 'value').set; setter.call(input, "
            f"{json.dumps(value)}); input.dispatchEvent(new Event('input', "
            "{ bubbles: true })); input.dispatchEvent(new Event('change', "
            "{ bubbles: true })); return true; })()"
        )
        if not await self.evaluate(expression):
            await self._report_safe_diagnostics("login form field lookup")
            raise AssertionError(f"Could not fill synthetic test field {selector}.")

    async def set_first_input(
        self,
        selectors: tuple[str, ...],
        value: str,
        stage: str,
    ) -> None:
        expression = (
            "(() => { const input = "
            f"{json.dumps(selectors)}.map(selector => document.querySelector(selector)).find(Boolean); "
            "if (!input) return false; "
            "const setter = Object.getOwnPropertyDescriptor("
            "HTMLInputElement.prototype, 'value').set; setter.call(input, "
            f"{json.dumps(value)}); input.dispatchEvent(new Event('input', "
            "{ bubbles: true })); input.dispatchEvent(new Event('change', "
            "{ bubbles: true })); return true; })()"
        )
        if not await self.evaluate(expression):
            await self._report_safe_diagnostics(stage)
            raise AssertionError(f"Could not fill {stage}.")

    async def check_consent(self) -> None:
        expression = """(() => {
            const checkbox = document.querySelector('input[type="checkbox"]');
            if (!checkbox) return false;
            if (!checkbox.checked) checkbox.click();
            return checkbox.checked;
        })()"""
        if not await self.evaluate(expression):
            raise AssertionError("The synthetic member contact-sharing consent was unavailable.")

    async def screenshot(self, filename: str) -> None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        result = await self.call("Page.captureScreenshot", {"format": "png"})
        path = EVIDENCE_DIR / filename
        path.write_bytes(base64.b64decode(result["data"]))
        CAPTURED_SCREENSHOTS.append(path)

    async def login(self, *, role: str, email: str) -> None:
        if role == "member":
            await self.navigate("/login")
            await self.wait_for(
                "!!document.querySelector('#member-email') || "
                "!!document.querySelector('[data-testid=\"member-login-form\"] input[type=\"email\"]')",
                "synthetic member login form",
            )
            await self.set_first_input(
                (
                    "#member-email",
                    '[data-testid="member-login-form"] input[type="email"]',
                    '[data-testid="member-login-form"] input[autocomplete="username email"]',
                ),
                email,
                "member login email field",
            )
            await self.set_first_input(
                (
                    "#member-password",
                    '[data-testid="member-login-form"] input[type="password"]',
                    '[data-testid="member-login-form"] input[autocomplete="current-password"]',
                ),
                SMOKE_PASSWORD,
                "member login password field",
            )
            button = "Sign in"
        elif role == "provider":
            await self.navigate("/provider/login")
            await self.wait_for(
                "!!document.querySelector('#provider-login-email') || "
                "!!document.querySelector('[data-testid=\"provider-login-form\"] input[type=\"email\"]')",
                "synthetic provider login form",
            )
            await self.set_first_input(
                (
                    "#provider-login-email",
                    '[data-testid="provider-login-form"] input[type="email"]',
                    '[data-testid="provider-login-form"] input[autocomplete="username email"]',
                ),
                email,
                "provider login email field",
            )
            await self.set_first_input(
                (
                    "#provider-login-password",
                    '[data-testid="provider-login-form"] input[type="password"]',
                    '[data-testid="provider-login-form"] input[autocomplete="current-password"]',
                ),
                SMOKE_PASSWORD,
                "provider login password field",
            )
            button = "Sign in to provider portal"
        else:
            raise ValueError("Unsupported synthetic browser role.")
        await self.click_text(button)
        await self.wait_for(
            "location.pathname !== '/login' && location.pathname !== '/provider/login'",
            f"synthetic {role} authentication",
        )


class ChromiumProcess:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.profile_dir = tempfile.TemporaryDirectory(prefix="private-messaging-smoke-chrome-")
        self.browser: Browser | None = None

    async def start(self) -> Browser:
        executable = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
            or shutil.which("google-chrome")
        )
        if not executable:
            raise RuntimeError("Chromium is required for this browser smoke.")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            cdp_port = sock.getsockname()[1]
        self.process = subprocess.Popen(
            [
                executable,
                "--headless=new",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--no-first-run",
                f"--remote-debugging-port={cdp_port}",
                f"--user-data-dir={self.profile_dir.name}",
                "about:blank",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        target = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Disposable Chromium failed to start.")
            try:
                with urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1) as response:
                    targets = json.load(response)
                target = next((item for item in targets if item.get("type") == "page"), None)
                if target and target.get("webSocketDebuggerUrl"):
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)
        if target is None:
            raise RuntimeError("Disposable Chromium did not expose a CDP page.")
        self.browser = Browser(target["webSocketDebuggerUrl"], self.profile_dir)
        await self.browser.connect()
        return self.browser

    async def close(self) -> None:
        if self.browser is not None:
            await self.browser.close()
            self.browser = None
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        # The browser profile is disposable and contains no refresh cookie.
        self.profile_dir.cleanup()


def _assert_no_stranger_conversation(database: IsolatedDatabase, seed: Seed) -> None:
    from app.models.messaging import ProviderConversation

    with Session(database.engine) as session:
        conversation_id = session.scalar(
            select(ProviderConversation.id).where(
                ProviderConversation.member_user_id == UUID(seed.stranger_id),
                ProviderConversation.provider_id == UUID(seed.provider_id),
            )
        )
        if conversation_id is not None:
            raise AssertionError("Fail-closed encryption checks saved a stranger conversation.")


def _response_seen(browser: Browser, method: str, path: str, status: int) -> bool:
    return browser.statuses[(method, path, status)] > 0


async def _run_scenario(
    database: IsolatedDatabase,
    seed: Seed,
    backend: BackendProcess,
) -> dict[str, int]:
    member_chrome = ChromiumProcess()
    provider_chrome = ChromiumProcess()
    stranger_chrome = ChromiumProcess()
    member: Browser | None = None
    provider: Browser | None = None
    stranger: Browser | None = None
    failure_backend: BackendProcess | None = None
    try:
        member = await member_chrome.start()
        provider = await provider_chrome.start()
        stranger = await stranger_chrome.start()
        for browser in (member, provider, stranger):
            browser.backend_url = backend.base_url

        # The member follows the actual profile action into the real contact
        # preview and consent-gated conversation form.
        await member.login(role="member", email=seed.member_email)
        await member.navigate_in_app(f"/providers/{seed.provider_id}")
        await member.wait_for_text(PROVIDER_NAME, "synthetic member provider profile")
        await member.wait_for_text("Message provider", "available profile Message provider action")
        await member.screenshot("synthetic-provider-profile.png")
        await member.click_text("Message provider")
        await member.wait_for_text("Before you send", "member contact preview")
        await member.wait_for_text(seed.member_email, "synthetic member email preview")
        await member.wait_for_text(MEMBER_PHONE, "synthetic member phone preview")
        await member.screenshot("synthetic-member-contact-preview.png")
        if await member.evaluate("document.querySelector('input[type=checkbox]')?.checked"):
            raise AssertionError("Consent was unexpectedly selected before member action.")
        await member.set_input("#first-private-message", INITIAL_BODY)
        await member.click_text("Send private message")
        await member.wait_for_text(
            "Please agree to share the contact details shown above with this provider.",
            "consent requirement",
        )
        await member.check_consent()
        member.force_server_consent_rejection = True
        await member.click_text("Send private message")
        await member.wait_for_text(
            "Agree to share your name, account email, and phone number with this provider before sending.",
            "server-enforced contact-sharing consent",
        )
        if not member.server_consent_rejection_seen or not _response_seen(
            member, "POST", "/api/v1/messages/start", 422
        ):
            raise AssertionError("The isolated API did not enforce contact-sharing consent.")
        from app.models.messaging import ProviderConversation

        with Session(database.engine) as session:
            if session.scalar(
                select(ProviderConversation.id).where(
                    ProviderConversation.member_user_id == UUID(seed.member_id),
                    ProviderConversation.provider_id == UUID(seed.provider_id),
                )
            ) is not None:
                raise AssertionError("The API persisted a conversation without member consent.")
        await member.click_text("Send private message")
        await member.wait_for(
            "location.pathname.startsWith('/member/messages/')",
            "saved synthetic member conversation",
        )
        conversation_path = await member.evaluate("location.pathname")
        conversation_id = conversation_path.rsplit("/", 1)[-1]
        await member.wait_for_text(INITIAL_BODY, "initial member message")
        member_private_contact_seen = await member.evaluate(
            "!!document.querySelector('[aria-labelledby=\"member-contact-title\"]')"
        )
        if member_private_contact_seen:
            raise AssertionError("The member saw the provider-only contact snapshot.")
        if await member.evaluate(
            f"document.body.innerText.includes({json.dumps(seed.member_email)})"
        ):
            raise AssertionError("The member saw their contact snapshot in the saved thread.")
        if await member.evaluate(
            f"document.body.innerText.includes({json.dumps(MEMBER_PHONE)})"
        ):
            raise AssertionError("The member saw their phone snapshot in the saved thread.")

        # Provider login is a separate disposable browser profile, so member
        # auth state and cookies are never shared across participants.
        await provider.login(role="provider", email=seed.provider_email)
        await provider.navigate_in_app("/provider/messages")
        await provider.wait_for_text("Member conversation", "provider inbox conversation")
        provider_thread_path = f"/provider/messages/{conversation_id}"
        await provider.click_conversation(provider_thread_path)
        await provider.wait_for_text("Member contact", "provider-only contact snapshot")
        await provider.wait_for_text(seed.member_email, "provider contact email")
        await provider.wait_for_text(MEMBER_PHONE, "provider contact phone")
        await provider.wait_for_text(INITIAL_BODY, "provider received initial message")
        await provider.screenshot("synthetic-provider-inbox-thread.png")
        await provider.set_input("#private-message-reply", REPLY_BODY)
        await provider.click_text("Send reply")
        await provider.wait_for_text(REPLY_BODY, "provider reply")
        await member.click_text("← Back to inbox")
        await member.wait_for_text(PROVIDER_NAME, "member inbox conversation")
        await member.click_conversation(conversation_path)
        await member.wait_for_text(REPLY_BODY, "member received provider reply")

        # Confirm no plaintext was written to the isolated PostgreSQL tables.
        stored_message_count = _conversation_storage_check(database, seed)
        smtp_count_before_restart = 0
        smtp_deadline = time.monotonic() + 8
        while smtp_count_before_restart < 3 and time.monotonic() < smtp_deadline:
            smtp_count_before_restart = await asyncio.to_thread(backend.smtp_event_count)
            if smtp_count_before_restart < 3:
                await asyncio.sleep(0.1)
        if smtp_count_before_restart < 3:
            raise AssertionError("SMTP stub did not record the expected safe event count.")

        # Restart only the disposable backend, with the same protected key
        # settings, same schema, and same key mode. App tokens remain in JS
        # memory; returning to inbox and reopening threads exercises fresh API
        # reads without storing auth tokens in browser storage.
        backend.stop()
        backend.start()
        for browser in (member, provider, stranger):
            browser.backend_url = backend.base_url
        await member.click_text("← Back to inbox")
        await member.wait_for_text(PROVIDER_NAME, "member inbox after backend restart")
        await member.click_conversation(conversation_path)
        await member.wait_for_text(INITIAL_BODY, "member initial message after restart")
        await member.wait_for_text(REPLY_BODY, "member reply after backend restart")
        await provider.click_text("← Back to inbox")
        await provider.wait_for_text("Member conversation", "provider inbox after backend restart")
        await provider.click_conversation(provider_thread_path)
        await provider.wait_for_text(INITIAL_BODY, "provider initial message after restart")
        await provider.wait_for_text(REPLY_BODY, "provider reply after restart")
        await provider.wait_for_text(seed.member_email, "provider contact after restart")
        await member.screenshot("synthetic-member-thread-after-restart.png")
        await provider.screenshot("synthetic-provider-thread-after-restart.png")
        if _conversation_storage_check(database, seed) != stored_message_count:
            raise AssertionError("Backend restart changed the saved encrypted message count.")

        # The synthetic stranger is a real verified member but is not a thread
        # participant. The API and browser UI must both deny conversation reads.
        await stranger.login(role="member", email=seed.stranger_email)
        await stranger.navigate_in_app(f"/member/messages/{conversation_id}")
        await stranger.wait_for_text("Conversation not found.", "participant isolation denial")
        outsider_inbox_empty = await stranger.evaluate(
            "document.querySelector('aside[aria-label=\"Message conversations\"]')"
            "?.innerText.includes('Your inbox is empty')"
        )
        if not outsider_inbox_empty:
            raise AssertionError("The synthetic stranger received a private inbox item.")
        if not _response_seen(
            stranger, "GET", f"/api/v1/messages/{conversation_id}", 404
        ):
            raise AssertionError("The isolated backend did not reject outsider thread access.")
        for private_value in (INITIAL_BODY, REPLY_BODY, seed.member_email, MEMBER_PHONE):
            if await stranger.evaluate(
                f"document.body.innerText.includes({json.dumps(private_value)})"
            ):
                raise AssertionError("The synthetic stranger saw participant-only conversation data.")

        # Prepare the stranger's actual UI start form while valid encryption is
        # available, then route its form submission to separate fail-closed
        # backend processes. Neither failure-mode process changes environment
        # settings or writes a conversation.
        await stranger.navigate_in_app(f"/providers/{seed.provider_id}")
        await stranger.wait_for_text("Message provider", "stranger provider profile")
        await stranger.click_text("Message provider")
        await stranger.wait_for_text("Before you send", "stranger synthetic contact preview")

        failure_backend = BackendProcess(8009, seed.schema, "missing")
        failure_backend.start()
        stranger.backend_url = failure_backend.base_url
        await stranger.set_input("#first-private-message", FAILURE_BODY)
        await stranger.check_consent()
        await stranger.click_text("Send private message")
        await stranger.wait_for_text(
            "Private messaging is temporarily unavailable.",
            "missing-key send fails closed",
        )
        if not _response_seen(stranger, "POST", "/api/v1/messages/start", 503):
            raise AssertionError("Missing-key start was not rejected by the real isolated API.")
        _assert_no_stranger_conversation(database, seed)

        # Contact links on the real provider profile remain available while the
        # key is absent, and the UI reports that messaging is unavailable.
        await stranger.navigate_in_app(f"/providers/{seed.provider_id}")
        await stranger.wait_for_text(
            "Private messaging is temporarily unavailable. Direct contact options remain available.",
            "direct contact fallback with missing key",
        )
        direct_contacts_available = await stranger.evaluate(
            f"!!document.querySelector('a[href=\"mailto:{LISTING_EMAIL}\"]')"
            " && !!document.querySelector('a[href^=\"tel:\"]')"
        )
        if not direct_contacts_available:
            raise AssertionError("Direct provider contact links disappeared with missing encryption.")
        await stranger.screenshot("synthetic-profile-direct-contacts-key-unavailable.png")

        failure_backend.stop()
        failure_backend = BackendProcess(8009, seed.schema, "invalid")
        failure_backend.start()
        stranger.backend_url = backend.base_url
        await stranger.navigate_in_app(f"/member/messages?provider_id={seed.provider_id}")
        await stranger.wait_for_text("Before you send", "invalid-key test start form")
        stranger.backend_url = failure_backend.base_url
        await stranger.set_input("#first-private-message", FAILURE_BODY)
        await stranger.check_consent()
        await stranger.click_text("Send private message")
        await stranger.wait_for_text(
            "Private messaging is temporarily unavailable.",
            "invalid-key send fails closed",
        )
        if not _response_seen(stranger, "POST", "/api/v1/messages/start", 503):
            raise AssertionError("Invalid-key start was not rejected by the real isolated API.")
        _assert_no_stranger_conversation(database, seed)

        await stranger.navigate_in_app(f"/providers/{seed.provider_id}")
        await stranger.wait_for_text(
            "Private messaging is temporarily unavailable. Direct contact options remain available.",
            "direct contact fallback with invalid key",
        )
        if not await stranger.evaluate(
            f"!!document.querySelector('a[href=\"mailto:{LISTING_EMAIL}\"]')"
            " && !!document.querySelector('a[href^=\"tel:\"]')"
        ):
            raise AssertionError("Direct provider contacts were unavailable during invalid-key failure.")
        await stranger.screenshot("synthetic-profile-direct-contacts-invalid-key.png")

        if member.transport_error_count or provider.transport_error_count or stranger.transport_error_count:
            raise AssertionError("CDP API routing encountered a transport error.")
        return {
            "stored_messages": stored_message_count,
            "smtp_stub_events": smtp_count_before_restart,
            "member_api_requests": member.api_request_count,
            "provider_api_requests": provider.api_request_count,
            "stranger_api_requests": stranger.api_request_count,
        }
    finally:
        if failure_backend is not None:
            failure_backend.stop()
        await asyncio.gather(
            *(process.close() for process in (member_chrome, provider_chrome, stranger_chrome)),
            return_exceptions=True,
        )


async def _main() -> None:
    database_url = _assert_frontend_and_prerequisites()
    schema = f"pm_smoke_{os.getpid()}_{secrets.token_hex(5)}"
    schema_created = False
    database: IsolatedDatabase | None = None
    backend: BackendProcess | None = None
    try:
        _create_schema(database_url, schema)
        schema_created = True
        database = IsolatedDatabase(database_url, schema)
        seed = _seed_schema(database, schema)
        backend = BackendProcess(8008, schema, "valid")
        backend.start()
        result = await _run_scenario(database, seed, backend)
        backend.stop()
        print("Private messaging isolated browser/API smoke passed.")
        print(
            "Assertions: profile-to-message flow, contact preview and consent, both inboxes, "
            "provider reply, participant-only reads, encrypted-at-rest records, restart persistence, "
            "and missing/invalid-key fail-closed with direct contacts available."
        )
        print(
            f"Safe counts: encrypted messages={result['stored_messages']}; "
            f"SMTP no-op events={result['smtp_stub_events']}; "
            f"intercepted API requests={result['member_api_requests'] + result['provider_api_requests'] + result['stranger_api_requests']}."
        )
        print(f"Screenshot evidence: {EVIDENCE_DIR.relative_to(ROOT)}/")
        for path in CAPTURED_SCREENSHOTS:
            print(f"  {path.relative_to(ROOT)}")
    finally:
        if backend is not None:
            backend.stop()
        if database is not None:
            database.close()
        if schema_created:
            _drop_owned_schema(database_url, schema)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("Private messaging isolated smoke interrupted; owned resources are cleaned in finally.")
        raise SystemExit(130)
    except Exception as exc:
        # Keep error reporting deliberately generic: never echo exception text,
        # which could contain an API payload, connection string, or credential.
        print(f"Private messaging isolated smoke failed safely ({type(exc).__name__}).")
        raise SystemExit(1)