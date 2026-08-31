"""Public subscriber registration and administrator directory coverage."""
import csv
import io
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from app.core.security import hash_password
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.enums import EmailDeliveryStatus, EmailPurpose, SubscriberRegistrationType
from app.models.subscriber import Subscriber
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.subscriber_service import SubscriberService
from tests.conftest import TestingSessionLocal


PUBLIC_URL = "/api/v1/public/subscribers"
ADMIN_URL = "/api/v1/admin/subscribers"
EXPORT_URL = f"{ADMIN_URL}/export"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client, seeded_admin) -> str:
    admin, password = seeded_admin
    response = client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_public_registration_normalizes_email_and_is_idempotent(client, db, monkeypatch):
    sent_to: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_subscriber_confirmation_email",
        lambda _self, recipient: sent_to.append(recipient),
    )

    first = client.post(
        PUBLIC_URL,
        json={"email": "RIDER@EXAMPLE.COM", "registration_type": "HORSE_OWNER"},
    )
    repeated = client.post(
        PUBLIC_URL,
        json={"email": "rider@example.com", "registration_type": "VET"},
    )

    assert first.status_code == 201
    assert repeated.status_code == 201
    assert sent_to == ["rider@example.com"]
    subscribers = db.query(Subscriber).all()
    assert len(subscribers) == 1
    assert subscribers[0].email == "rider@example.com"
    assert subscribers[0].registration_type == SubscriberRegistrationType.HORSE_OWNER.value
    attempts = db.query(EmailDeliveryLog).all()
    assert len(attempts) == 1
    assert attempts[0].purpose == EmailPurpose.SUBSCRIBER_CONFIRMATION.value
    assert attempts[0].status == EmailDeliveryStatus.SUCCESS.value


def test_failed_confirmation_is_retryable_without_duplicate_subscriber(client, db, monkeypatch):
    def fail_delivery(_self, _recipient):
        raise EmailDeliveryError("Unable to deliver email.")

    monkeypatch.setattr(EmailService, "send_subscriber_confirmation_email", fail_delivery)
    failed = client.post(
        PUBLIC_URL,
        json={"email": "retry@example.com", "registration_type": "VET"},
    )
    assert failed.status_code == 502
    assert db.query(Subscriber).count() == 1
    failed_log = db.query(EmailDeliveryLog).one()
    assert failed_log.status == EmailDeliveryStatus.FAILED.value
    assert failed_log.failure_message == "Unable to deliver email."

    monkeypatch.setattr(
        EmailService, "send_subscriber_confirmation_email", lambda *_args: None
    )
    retried = client.post(
        PUBLIC_URL,
        json={"email": "retry@example.com", "registration_type": "VET"},
    )
    assert retried.status_code == 201
    assert db.query(Subscriber).count() == 1
    assert [
        row.status for row in db.query(EmailDeliveryLog).order_by(EmailDeliveryLog.created_at)
    ] == [EmailDeliveryStatus.FAILED.value, EmailDeliveryStatus.SUCCESS.value]


def test_unresolved_pending_confirmation_is_retried(client, db, monkeypatch):
    delivered: list[str] = []
    monkeypatch.setattr(
        EmailService,
        "send_subscriber_confirmation_email",
        lambda _self, recipient: delivered.append(recipient),
    )
    from app.repositories.email_delivery_repository import EmailDeliveryRepository

    original_complete = EmailDeliveryRepository.complete_durable_attempt
    monkeypatch.setattr(
        EmailDeliveryRepository,
        "complete_durable_attempt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    first = client.post(
        PUBLIC_URL,
        json={"email": "pending@example.com", "registration_type": "CLINIC"},
    )
    assert first.status_code == 502
    assert db.query(EmailDeliveryLog).one().status == EmailDeliveryStatus.PENDING.value

    monkeypatch.setattr(EmailDeliveryRepository, "complete_durable_attempt", original_complete)
    retried = client.post(
        PUBLIC_URL,
        json={"email": "pending@example.com", "registration_type": "CLINIC"},
    )
    assert retried.status_code == 201
    assert delivered == ["pending@example.com", "pending@example.com"]
    assert [
        entry.status for entry in db.query(EmailDeliveryLog).order_by(EmailDeliveryLog.created_at)
    ] == [EmailDeliveryStatus.PENDING.value, EmailDeliveryStatus.SUCCESS.value]


def test_racing_submissions_send_only_one_confirmation(db, monkeypatch):
    first_send_started = Event()
    release_first_send = Event()
    send_lock = Lock()
    sent_to: list[str] = []

    def send_confirmation(_self, recipient):
        with send_lock:
            sent_to.append(recipient)
            is_first = len(sent_to) == 1
        if is_first:
            first_send_started.set()
            assert release_first_send.wait(timeout=5)

    monkeypatch.setattr(EmailService, "send_subscriber_confirmation_email", send_confirmation)

    def register() -> bool:
        session = TestingSessionLocal()
        try:
            return SubscriberService(session).register(
                email="race@example.com",
                registration_type=SubscriberRegistrationType.HOSPITAL,
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(register)
        assert first_send_started.wait(timeout=5)
        second = executor.submit(register)
        release_first_send.set()
        assert first.result(timeout=5) is True
        assert second.result(timeout=5) is True

    assert sent_to == ["race@example.com"]
    assert db.query(Subscriber).filter_by(email="race@example.com").count() == 1
    assert (
        db.query(EmailDeliveryLog)
        .filter_by(purpose=EmailPurpose.SUBSCRIBER_CONFIRMATION.value)
        .count()
        == 1
    )


def test_public_registration_validates_email_and_registration_type(client):
    invalid_email = client.post(
        PUBLIC_URL,
        json={"email": "not-an-email", "registration_type": "VET"},
    )
    invalid_type = client.post(
        PUBLIC_URL,
        json={"email": "valid@example.com", "registration_type": "UNSUPPORTED"},
    )
    assert invalid_email.status_code == 422
    assert invalid_type.status_code == 422


def test_subscriber_directory_requires_an_administrator(client, db, seeded_admin):
    assert client.get(ADMIN_URL).status_code == 401
    assert client.get(EXPORT_URL).status_code == 401
    repo = UserRepository(db)
    role = repo.get_role_by_name("horse_owner") or repo.create_role(
        "horse_owner", "Horse owner"
    )
    member = repo.create_user(
        email="member@example.com",
        password_hash=hash_password("HorseCare2026"),
        role=role,
        first_name="Member",
        last_name="Example",
    )
    member.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "HorseCare2026"},
    )
    assert login.status_code == 200
    assert client.get(ADMIN_URL, headers=_auth(login.json()["access_token"])).status_code == 403
    assert client.get(EXPORT_URL, headers=_auth(login.json()["access_token"])).status_code == 403


def test_admin_can_search_filter_and_page_subscribers(client, db, seeded_admin):
    db.add_all(
        [
            Subscriber(
                email="owner@example.com",
                registration_type=SubscriberRegistrationType.HORSE_OWNER.value,
                submitted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="vet@example.com",
                registration_type=SubscriberRegistrationType.VET.value,
                submitted_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()
    response = client.get(
        ADMIN_URL,
        params={"search": "vet", "registration_type": "VET", "page_size": 10},
        headers=_auth(_admin_token(client, seeded_admin)),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {"page": 1, "page_size": 10, "total": 1, "total_pages": 1}
    assert payload["data"][0]["email"] == "vet@example.com"
    assert payload["data"][0]["registration_type"] == "VET"


def test_admin_directory_filters_submission_dates_in_the_system_timezone(
    client, db, seeded_admin
):
    token = _admin_token(client, seeded_admin)
    settings = client.patch(
        "/api/v1/admin/system-settings",
        json={
            "timezone": "America/New_York",
            "date_format": "month_day_year",
            "time_format": "12_hour",
        },
        headers=_auth(token),
    )
    assert settings.status_code == 200, settings.text
    db.add_all(
        [
            Subscriber(
                email="before@example.com",
                registration_type=SubscriberRegistrationType.OTHER.value,
                submitted_at=datetime(2026, 1, 2, 4, 59, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="start@example.com",
                registration_type=SubscriberRegistrationType.VET.value,
                submitted_at=datetime(2026, 1, 2, 5, 0, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="end@example.com",
                registration_type=SubscriberRegistrationType.CLINIC.value,
                submitted_at=datetime(2026, 1, 3, 4, 59, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="after@example.com",
                registration_type=SubscriberRegistrationType.HOSPITAL.value,
                submitted_at=datetime(2026, 1, 3, 5, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    selected_day = client.get(
        ADMIN_URL,
        params={"date_from": "2026-01-02", "date_to": "2026-01-02", "page_size": 100},
        headers=_auth(token),
    )
    assert selected_day.status_code == 200, selected_day.text
    assert [row["email"] for row in selected_day.json()["data"]] == [
        "end@example.com",
        "start@example.com",
    ]

    from_only = client.get(
        ADMIN_URL,
        params={"date_from": "2026-01-02", "page_size": 100},
        headers=_auth(token),
    )
    assert [row["email"] for row in from_only.json()["data"]] == [
        "after@example.com",
        "end@example.com",
        "start@example.com",
    ]

    to_only = client.get(
        ADMIN_URL,
        params={"date_to": "2026-01-02", "page_size": 100},
        headers=_auth(token),
    )
    assert [row["email"] for row in to_only.json()["data"]] == [
        "end@example.com",
        "start@example.com",
        "before@example.com",
    ]


def test_subscriber_date_range_validation_applies_to_directory_and_export(
    client, seeded_admin
):
    headers = _auth(_admin_token(client, seeded_admin))
    for url in (ADMIN_URL, EXPORT_URL):
        response = client.get(
            url,
            params={"date_from": "2026-02-01", "date_to": "2026-01-31"},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["detail"] == {
            "code": "invalid_date_range",
            "message": "Start date must be on or before end date.",
        }


def test_admin_can_export_every_matching_subscriber_as_a_csv(client, db, seeded_admin):
    db.add_all(
        [
            Subscriber(
                email="vet-older@example.com",
                registration_type=SubscriberRegistrationType.VET.value,
                submitted_at=datetime(2026, 8, 20, 12, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="vet-newer@example.com",
                registration_type=SubscriberRegistrationType.VET.value,
                submitted_at=datetime(2026, 8, 21, 12, tzinfo=timezone.utc),
            ),
            Subscriber(
                email="clinic@example.com",
                registration_type=SubscriberRegistrationType.CLINIC.value,
                submitted_at=datetime(2026, 8, 21, 13, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    response = client.get(
        EXPORT_URL,
        params={
            "search": "vet",
            "registration_type": "VET",
            "date_from": "2026-08-20",
            "date_to": "2026-08-21",
        },
        headers=_auth(_admin_token(client, seeded_admin)),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv; charset=utf-8")
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="equiconnected-subscribers-'
    )
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows == [
        ["Email address", "Registration type", "Submitted timestamp"],
        ["vet-newer@example.com", "VET", "2026-08-21T12:00:00+00:00"],
        ["vet-older@example.com", "VET", "2026-08-20T12:00:00+00:00"],
    ]
    from app.models.audit_log import AuditLog

    audit_event = db.query(AuditLog).filter_by(action="subscriber.exported").one()
    assert audit_event.event_metadata["exported_count"] == 2