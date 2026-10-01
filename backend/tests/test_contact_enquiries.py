"""Administrator access and filtering for persisted contact enquiries."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.security import hash_password
from app.core.rate_limit import _contact_attempts
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.contact_enquiry import ContactEnquiry
from app.models.enums import ContactEnquiryType, EmailPurpose
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.api.v1 import public


ADMIN_URL = "/api/v1/admin/contact-enquiries"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client, seeded_admin) -> str:
    admin, password = seeded_admin
    response = client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _enquiry(
    *,
    name: str,
    email: str,
    enquiry_type: ContactEnquiryType = ContactEnquiryType.GENERAL,
    phone: str | None = None,
    message: str = "I would like to learn more about care.",
    submitted_at: datetime,
) -> ContactEnquiry:
    return ContactEnquiry(
        name=name,
        email=email,
        enquiry_type=enquiry_type.value,
        phone=phone,
        message=message,
        submitted_at=submitted_at,
    )


def test_contact_enquiry_list_and_detail_require_admin(client, db, seeded_admin):
    assert client.get(ADMIN_URL).status_code == 401
    enquiry = _enquiry(
        name="Member Sender",
        email="sender@example.com",
        submitted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    db.add(enquiry)
    db.commit()

    user_repo = UserRepository(db)
    role = user_repo.get_role_by_name("horse_owner") or user_repo.create_role(
        "horse_owner", "Horse owner"
    )
    member = user_repo.create_user(
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
    member_headers = _auth(login.json()["access_token"])
    assert client.get(ADMIN_URL, headers=member_headers).status_code == 403
    assert (
        client.get(f"{ADMIN_URL}/{enquiry.id}", headers=member_headers).status_code
        == 403
    )

    admin_headers = _auth(_admin_token(client, seeded_admin))
    assert client.get(ADMIN_URL, headers=admin_headers).status_code == 200
    assert client.get(
        f"{ADMIN_URL}/{enquiry.id}", headers=admin_headers
    ).status_code == 200


def test_admin_contact_enquiries_search_filter_and_paginate(client, db, seeded_admin):
    base_time = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    db.add_all(
        [
            _enquiry(
                name="First Sender",
                email="first@example.com",
                enquiry_type=ContactEnquiryType.GENERAL,
                phone="+971 50 111 1111",
                message="Could you share the available details?",
                submitted_at=base_time,
            ),
            _enquiry(
                name="Second Sender",
                email="second@example.com",
                enquiry_type=ContactEnquiryType.LISTING,
                phone="+971 50 222 2222",
                message="I want to list my equine practice.",
                submitted_at=datetime(2026, 8, 20, 12, 1, tzinfo=timezone.utc),
            ),
            _enquiry(
                name="Third Sender",
                email="third@example.com",
                enquiry_type=ContactEnquiryType.PARTNERSHIP,
                phone=None,
                message="A multiline message\nabout a partnership.",
                submitted_at=datetime(2026, 8, 21, 12, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()
    headers = _auth(_admin_token(client, seeded_admin))

    page = client.get(
        ADMIN_URL,
        params={"page": 1, "page_size": 2},
        headers=headers,
    )
    assert page.status_code == 200, page.text
    payload = page.json()
    assert payload["meta"] == {"page": 1, "page_size": 2, "total": 3, "total_pages": 2}
    assert [row["name"] for row in payload["data"]] == [
        "Third Sender",
        "Second Sender",
    ]

    page_two = client.get(
        ADMIN_URL,
        params={"page": 2, "page_size": 2},
        headers=headers,
    )
    assert [row["name"] for row in page_two.json()["data"]] == ["First Sender"]

    combined = client.get(
        ADMIN_URL,
        params={
            "search": "equine",
            "enquiry_type": "listing",
            "date_from": "2026-08-20",
            "date_to": "2026-08-20",
            "page_size": 100,
        },
        headers=headers,
    )
    assert combined.status_code == 200
    assert [row["email"] for row in combined.json()["data"]] == ["second@example.com"]

    phone_search = client.get(
        ADMIN_URL,
        params={"search": "+971 50 111", "page_size": 100},
        headers=headers,
    )
    assert [row["name"] for row in phone_search.json()["data"]] == ["First Sender"]


def test_contact_enquiry_date_filters_use_configured_timezone(client, db, seeded_admin):
    headers = _auth(_admin_token(client, seeded_admin))
    settings = client.patch(
        "/api/v1/admin/system-settings",
        json={
            "timezone": "America/New_York",
            "date_format": "month_day_year",
            "time_format": "12_hour",
        },
        headers=headers,
    )
    assert settings.status_code == 200, settings.text
    db.add_all(
        [
            _enquiry(
                name="Before Date",
                email="before@example.com",
                submitted_at=datetime(2026, 1, 2, 4, 59, tzinfo=timezone.utc),
            ),
            _enquiry(
                name="On Date Start",
                email="start@example.com",
                submitted_at=datetime(2026, 1, 2, 5, 0, tzinfo=timezone.utc),
            ),
            _enquiry(
                name="On Date End",
                email="end@example.com",
                submitted_at=datetime(2026, 1, 3, 4, 59, tzinfo=timezone.utc),
            ),
            _enquiry(
                name="After Date",
                email="after@example.com",
                submitted_at=datetime(2026, 1, 3, 5, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()
    response = client.get(
        ADMIN_URL,
        params={"date_from": "2026-01-02", "date_to": "2026-01-02", "page_size": 100},
        headers=headers,
    )
    assert response.status_code == 200
    assert [row["email"] for row in response.json()["data"]] == [
        "end@example.com",
        "start@example.com",
    ]


def test_contact_enquiry_detail_returns_full_message_and_missing_record_is_404(
    client, db, seeded_admin
):
    message = "First line\nSecond line\n\nFinal line with all of its content."
    enquiry = _enquiry(
        name="Full Detail Sender",
        email="full@example.com",
        enquiry_type=ContactEnquiryType.OTHER,
        message=message,
        submitted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    db.add(enquiry)
    db.commit()
    headers = _auth(_admin_token(client, seeded_admin))

    detail = client.get(f"{ADMIN_URL}/{enquiry.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json() == {
        "id": str(enquiry.id),
        "name": "Full Detail Sender",
        "email": "full@example.com",
        "enquiry_type": "other",
        "phone": None,
        "message": message,
        "submitted_at": "2026-08-20T00:00:00Z",
    }

    missing = client.get(
        f"{ADMIN_URL}/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "contact_enquiry_not_found"


def test_contact_enquiry_list_rejects_invalid_range_and_bad_query_values(
    client, seeded_admin
):
    headers = _auth(_admin_token(client, seeded_admin))
    invalid_range = client.get(
        ADMIN_URL,
        params={"date_from": "2026-08-21", "date_to": "2026-08-20"},
        headers=headers,
    )
    assert invalid_range.status_code == 422
    assert invalid_range.json()["detail"] == {
        "code": "invalid_date_range",
        "message": "Start date must be on or before end date.",
    }
    assert client.get(
        ADMIN_URL,
        params={"enquiry_type": "emergency"},
        headers=headers,
    ).status_code == 422
    assert client.get(
        ADMIN_URL,
        params={"page_size": 101},
        headers=headers,
    ).status_code == 422


def test_admin_email_logs_keep_contact_confirmation_and_team_recipients_distinct(
    client, db, seeded_admin, monkeypatch
):
    _contact_attempts.clear()
    monkeypatch.setattr(
        public, "get_settings", lambda: SimpleNamespace(ADMIN_EMAIL="team@example.com")
    )
    # Both delivery methods are replaced so this integration test never uses SMTP.
    monkeypatch.setattr(
        EmailService, "send_contact_confirmation_email", lambda *_args: None
    )
    monkeypatch.setattr(
        EmailService, "send_contact_message", lambda *_args, **_kwargs: None
    )
    payload = {
        "name": "Repeat Sender",
        "email": "repeat@example.com",
        "enquiry_type": "general",
        "message": "Please contact me about the platform.",
    }

    first = client.post("/api/v1/public/contact", json=payload)
    second = client.post(
        "/api/v1/public/contact", json={**payload, "enquiry_type": "partnership"}
    )
    assert first.status_code == second.status_code == 202
    assert db.query(ContactEnquiry).filter_by(email=payload["email"]).count() == 2

    headers = _auth(_admin_token(client, seeded_admin))
    response = client.get("/api/v1/admin/email-logs", headers=headers)

    assert response.status_code == 200, response.text
    contact_rows = [
        row for row in response.json()["data"]
        if row["purpose"] in {
            "contact_confirmation",
            EmailPurpose.CONTACT_NOTIFICATION.value,
        }
    ]
    assert len(contact_rows) == 4
    assert len({row["id"] for row in contact_rows}) == 4
    assert {
        (row["purpose"], row["recipient_email"])
        for row in contact_rows
    } == {
        ("contact_confirmation", "repeat@example.com"),
        (EmailPurpose.CONTACT_NOTIFICATION.value, "team@example.com"),
    }
    assert all(row["status"] == "success" for row in contact_rows)
    assert db.query(EmailDeliveryLog).count() == 4