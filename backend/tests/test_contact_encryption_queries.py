"""Encrypted contact filtering and blind-index uniqueness compatibility."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

from app.models.enums import SubscriberRegistrationType
from app.models.subscriber import Subscriber
from app.repositories.subscriber_repository import SubscriberRepository
from tests.conftest import TestingSessionLocal


def test_subscriber_contact_search_scans_past_first_yield_batch(db):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(270):
        email = (
            f"deep-match-{index:02d}@example.invalid"
            if index < 10
            else f"ordinary-{index:03d}@example.invalid"
        )
        rows.append(
            Subscriber(
                email=email,
                registration_type=SubscriberRegistrationType.OTHER.value,
                submitted_at=start + timedelta(seconds=index),
            )
        )
    db.add_all(rows)
    db.commit()

    repository = SubscriberRepository(db)
    first_page, first_total = repository.list(
        search="deep-match",
        page=1,
        page_size=5,
    )
    second_page, second_total = repository.list(
        search="deep-match",
        page=2,
        page_size=5,
    )

    assert first_total == second_total == 10
    assert [row.email for row in first_page] == [
        f"deep-match-{index:02d}@example.invalid"
        for index in range(9, 4, -1)
    ]
    assert [row.email for row in second_page] == [
        f"deep-match-{index:02d}@example.invalid"
        for index in range(4, -1, -1)
    ]


def test_subscriber_blind_index_deduplicates_concurrent_normalized_writes(
    db, monkeypatch
):
    barrier = Barrier(2)
    original_get = SubscriberRepository.get_by_email

    def synchronize_absent_lookups(repository, email):
        existing = original_get(repository, email)
        if existing is None:
            barrier.wait(timeout=10)
        return existing

    monkeypatch.setattr(
        SubscriberRepository, "get_by_email", synchronize_absent_lookups
    )
    email = f"subscriber-race-{uuid4().hex}@example.invalid"

    def register(index):
        session = TestingSessionLocal()
        try:
            subscriber, created = SubscriberRepository(session).create_or_get(
                email=email.upper() if index else email,
                registration_type=SubscriberRegistrationType.OTHER,
            )
            return subscriber.id, created
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, range(2)))

    assert results[0][0] == results[1][0]
    assert sorted(created for _subscriber_id, created in results) == [False, True]
    assert db.query(Subscriber).filter(Subscriber.email == email.upper()).count() == 1