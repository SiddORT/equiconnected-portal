"""Shared PostgreSQL rate limiting for public postal-code lookups."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Lock

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from tests import conftest
from app.api.v1 import auth as auth_router
from app.db.session import get_db
from app.main import create_app
from app.models.postal_lookup_rate_limit import PostalLookupRateLimit


LOOKUP_URL = "/api/v1/auth/provider-postal-lookup"
IP_ONE = "198.51.100.11"
IP_TWO = "198.51.100.12"
MATCH_PAYLOAD = [
    {
        "display_name": "Austin, Texas, United States",
        "address": {
            "city": "Austin",
            "state": "Texas",
            "country": "United States",
            "country_code": "us",
            "postcode": "78701",
        },
    }
]


@contextmanager
def _postal_client(default_host=IP_ONE):
    """Create an app with an independent engine and request-scoped sessions."""
    engine = conftest._make_engine(conftest.TEST_SCHEMA)
    session_local = sessionmaker(engine, autocommit=False, autoflush=False)
    app = create_app()

    def _override_get_db():
        session = session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db

    @app.middleware("http")
    async def _set_test_remote_client(request, call_next):
        host = request.headers.get("x-test-client-host", default_host)
        request.scope["client"] = None if host == "__missing__" else (host, 12345)
        return await call_next(request)

    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        engine.dispose()


def _mock_nominatim(monkeypatch, *, payload=None):
    """Replace the outbound Nominatim client and expose a thread-safe call count."""
    state = {"payload": MATCH_PAYLOAD if payload is None else payload, "error": None}
    calls = []
    lock = Lock()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return state["payload"]

    class FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            with lock:
                calls.append(True)
            if state["error"] is not None:
                raise state["error"]
            return FakeResponse()

    monkeypatch.setattr(auth_router.httpx, "AsyncClient", FakeAsyncClient)
    return state, calls


def _key(host):
    return sha256(host.encode("utf-8")).hexdigest()


def _stored_row(engine, host):
    session = sessionmaker(engine, autocommit=False, autoflush=False)()
    try:
        return (
            session.query(PostalLookupRateLimit)
            .filter_by(key=_key(host))
            .one_or_none()
        )
    finally:
        session.close()


def _seed_attempts(engine, host, attempts, expires_at):
    session = sessionmaker(engine, autocommit=False, autoflush=False)()
    try:
        session.add(
            PostalLookupRateLimit(
                key=_key(host), attempts=attempts, expires_at=expires_at
            )
        )
        session.commit()
    finally:
        session.close()


def test_two_app_instances_share_atomic_ip_budget_under_concurrency(db, monkeypatch):
    _, calls = _mock_nominatim(monkeypatch)
    with ExitStack() as stack:
        client_one, engine_one = stack.enter_context(_postal_client(IP_ONE))
        client_two, _ = stack.enter_context(_postal_client(IP_ONE))
        clients = [client_one, client_two]

        def lookup(index):
            return clients[index % 2].get(
                LOOKUP_URL,
                params={"postal_code": "78701"},
            )

        with ThreadPoolExecutor(max_workers=40) as pool:
            responses = list(pool.map(lookup, range(40)))

        assert sum(response.status_code == 200 for response in responses) == 20
        limited = [response for response in responses if response.status_code == 429]
        assert len(limited) == 20
        assert all(
            response.json()["detail"]
            == {
                "code": "rate_limited",
                "message": "Too many postal lookup requests. Please try again later.",
            }
            for response in limited
        )
        assert all(response.headers["Retry-After"] == "60" for response in limited)
        success = next(response for response in responses if response.status_code == 200)
        assert success.json() == {
            "status": "match",
            "candidates": [
                {
                    "country": "United States",
                    "country_code": "US",
                    "state_province": "Texas",
                    "city": "Austin",
                    "postal_code": "78701",
                    "display_name": "Austin, Texas, United States",
                }
            ],
        }
        assert len(calls) == 20
        row = _stored_row(engine_one, IP_ONE)
        assert row is not None
        assert len(row.attempts) == 20


def test_ip_and_missing_client_buckets_are_independent(db, monkeypatch):
    _, calls = _mock_nominatim(monkeypatch)
    with _postal_client(IP_ONE) as (client, engine):
        for _ in range(20):
            assert client.get(LOOKUP_URL, params={"postal_code": "78701"}).status_code == 200

        other_ip = client.get(
            LOOKUP_URL,
            params={"postal_code": "78701"},
            headers={"x-test-client-host": IP_TWO},
        )
        assert other_ip.status_code == 200

        for _ in range(20):
            response = client.get(
                LOOKUP_URL,
                params={"postal_code": "78701"},
                headers={"x-test-client-host": "__missing__"},
            )
            assert response.status_code == 200

        missing_client_limited = client.get(
            LOOKUP_URL,
            params={"postal_code": "78701"},
            headers={"x-test-client-host": "__missing__"},
        )
        ip_limited = client.get(LOOKUP_URL, params={"postal_code": "78701"})
        assert missing_client_limited.status_code == 429
        assert ip_limited.status_code == 429
        assert len(calls) == 41
        assert len(_stored_row(engine, IP_ONE).attempts) == 20
        assert len(_stored_row(engine, IP_TWO).attempts) == 1
        assert len(_stored_row(engine, "unknown").attempts) == 20


def test_sliding_window_discards_expired_attempts_and_refills(db, monkeypatch):
    _, _ = _mock_nominatim(monkeypatch)
    now = datetime.now(timezone.utc)
    with _postal_client(IP_ONE) as (client, engine):
        mixed = [now - timedelta(seconds=61)] * 19 + [now - timedelta(seconds=30)]
        _seed_attempts(engine, IP_ONE, mixed, now + timedelta(seconds=30))

        allowed = client.get(LOOKUP_URL, params={"postal_code": "78701"})
        assert allowed.status_code == 200
        row = _stored_row(engine, IP_ONE)
        assert len(row.attempts) == 2

        expired_ip = IP_TWO
        _seed_attempts(
            engine,
            expired_ip,
            [now - timedelta(seconds=61)] * 20,
            now - timedelta(seconds=1),
        )
        refilled = client.get(
            LOOKUP_URL,
            params={"postal_code": "78701"},
            headers={"x-test-client-host": expired_ip},
        )
        assert refilled.status_code == 200
        assert len(_stored_row(engine, expired_ip).attempts) == 1

        # Freeze the database clock at a known instant to verify that an
        # attempt exactly 60 seconds old is still in the inclusive window.
        boundary_ip = "198.51.100.13"
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        boundary_attempts = [fixed_now - timedelta(seconds=60)] + [
            fixed_now - timedelta(seconds=30)
        ] * 19
        _seed_attempts(
            engine,
            boundary_ip,
            boundary_attempts,
            fixed_now + timedelta(seconds=30),
        )
        timestamp_literal = fixed_now.strftime("%Y-%m-%d %H:%M:%S%z")

        def _freeze_database_clock(_conn, _cursor, statement, parameters, _context, _many):
            frozen = f"TIMESTAMPTZ '{timestamp_literal}'"
            return statement.replace("clock_timestamp()", frozen), parameters

        event.listen(engine, "before_cursor_execute", _freeze_database_clock, retval=True)
        try:
            boundary = client.get(
                LOOKUP_URL,
                params={"postal_code": "78701"},
                headers={"x-test-client-host": boundary_ip},
            )
        finally:
            event.remove(engine, "before_cursor_execute", _freeze_database_clock)
        assert boundary.status_code == 429


def test_invalid_no_match_and_unavailable_lookups_all_consume_budget(db, monkeypatch):
    state, calls = _mock_nominatim(monkeypatch, payload=[])
    with _postal_client(IP_ONE) as (client, engine):
        invalid = client.get(LOOKUP_URL, params={"postal_code": "!!!"})
        assert invalid.status_code == 200
        assert invalid.json() == {"status": "no_match", "candidates": []}

        no_match = client.get(LOOKUP_URL, params={"postal_code": "78701"})
        assert no_match.status_code == 200
        assert no_match.json() == {"status": "no_match", "candidates": []}

        state["error"] = httpx.ConnectError("Nominatim unavailable")
        unavailable = client.get(LOOKUP_URL, params={"postal_code": "78701"})
        assert unavailable.status_code == 200
        assert unavailable.json() == {"status": "unavailable", "candidates": []}

        assert len(calls) == 2
        assert len(_stored_row(engine, IP_ONE).attempts) == 3


def test_limit_persists_after_recreating_the_app(db, monkeypatch):
    _, calls = _mock_nominatim(monkeypatch)
    with _postal_client(IP_ONE) as (client, _):
        first = client.get(LOOKUP_URL, params={"postal_code": "78701"})
        assert first.status_code == 200

    with _postal_client(IP_ONE) as (restarted_client, _):
        for _ in range(19):
            response = restarted_client.get(
                LOOKUP_URL, params={"postal_code": "78701"}
            )
            assert response.status_code == 200
        limited = restarted_client.get(
            LOOKUP_URL, params={"postal_code": "78701"}
        )
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
    assert len(calls) == 20


def test_database_failure_fails_closed_without_calling_nominatim(db, monkeypatch):
    _, calls = _mock_nominatim(monkeypatch)
    with _postal_client(IP_ONE) as (client, engine):
        @event.listens_for(engine, "before_cursor_execute")
        def _fail_database(*_args, **_kwargs):
            raise OperationalError(
                "simulated PostgreSQL failure", {}, RuntimeError("database offline")
            )

        response = client.get(LOOKUP_URL, params={"postal_code": "78701"})

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "code": "rate_limit_unavailable",
            "message": "Postal lookup is temporarily unavailable. Please try again later.",
        }
        assert response.headers["Retry-After"] == "60"
        assert calls == []


def test_stale_cleanup_is_bounded_and_skips_locked_and_active_buckets(db, monkeypatch):
    _mock_nominatim(monkeypatch)
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)
    db.add_all([
        PostalLookupRateLimit(
            key=_key(f"expired-{index}"),
            attempts=[stale_time],
            expires_at=stale_time + timedelta(seconds=60),
        )
        for index in range(105)
    ])
    db.add(PostalLookupRateLimit(
        key=_key(IP_TWO), attempts=[now], expires_at=now + timedelta(seconds=60),
    ))
    db.commit()
    with _postal_client(IP_ONE) as (client, engine):
        with sessionmaker(engine)() as locked:
            locked.query(PostalLookupRateLimit).filter_by(
                key=_key("expired-0"),
            ).with_for_update().one()
            response = client.get(LOOKUP_URL, params={"postal_code": "78701"})
            assert response.status_code == 200
            assert _stored_row(engine, "expired-0") is not None
            assert _stored_row(engine, IP_TWO) is not None
            with sessionmaker(engine)() as observer:
                assert observer.query(PostalLookupRateLimit).count() == 7
            locked.rollback()
