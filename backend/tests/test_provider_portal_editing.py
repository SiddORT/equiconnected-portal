"""Owner editing contracts; all writes use the isolated pytest schema."""
from datetime import date, timedelta
from io import BytesIO

from PIL import Image
import pytest

from app.main import app
from app.models.enums import DoctorAvailability, PublicationStatus, ProviderType
from app.models.language import Language, ProviderLanguage
from app.models.provider import DoctorVisit
from app.repositories.provider_repository import ProviderRepository
import app.services.provider_portal_service as portal_module
from tests.test_provider_profile_updates import _portal_doctor, _portal_provider, _login, _visit_addition, _legacy_draft


def headers(client, user, password="ProviderPass9"):
    return {"Authorization": f"Bearer {_login(client, user.email, password)}"}


@pytest.mark.parametrize("published", [False, True])
def test_names_languages_classification_and_visit_atomic_lifecycle(client, db, seeded_admin, published):
    admin, password = seeded_admin
    provider, user = _portal_doctor(db, admin, email="editing@example.com",
        publication_status=PublicationStatus.PUBLISHED if published else PublicationStatus.UNPUBLISHED)
    active = Language(name="Synthetic active", code="sx", is_active=True)
    inactive = Language(name="Synthetic retained", code="sy", is_active=False)
    db.add_all([active, inactive])
    db.flush()
    db.add(ProviderLanguage(provider_id=provider.id, language_id=inactive.id))
    db.commit()
    owner = headers(client, user)
    admin_headers = headers(client, admin, password)
    before = client.get("/api/v1/provider/portal/profile", headers=owner).json()
    assert before["editable_profile"]["doctor_availability"] is None
    assert before["editable_profile"]["first_name"] is None
    assert client.patch("/api/v1/provider/portal/profile", headers=owner, json={"website": "https://example.test"}).status_code == 200
    db.refresh(provider)
    assert provider.doctor_availability is None
    day = date.today() + timedelta(days=8)
    body = {
        "first_name": "Amina", "last_name": "Rider", "doctor_availability": "VISITING",
        "language_ids": [str(active.id), str(inactive.id)],
        "visit_additions": [_visit_addition(day, day)],
    }
    submitted = client.patch("/api/v1/provider/portal/profile", headers=owner, json=body)
    assert submitted.status_code == 200, submitted.text
    snapshot = submitted.json()["editable_profile"]
    assert snapshot["first_name"] == "Amina"
    assert set(snapshot["language_ids"]) == set(body["language_ids"])
    assert any(item["id"] == str(inactive.id) and not item["is_active"] for item in submitted.json()["language_choices"])
    assert submitted.json()["profile_update"] is None
    assert submitted.json()["editable_profile"]["visit_additions"] == []
    detail = client.get(f"/api/v1/admin/providers/{provider.id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "Amina Rider"
    assert detail.json()["doctor_availability"] == "VISITING"
    assert len(detail.json()["doctor_visits"]) == 1
    db.expire_all()
    saved = ProviderRepository(db).get_by_id(provider.id)
    assert saved.name == "Amina Rider"
    assert saved.doctor_profile.first_name == "Amina"
    assert saved.doctor_availability == DoctorAvailability.VISITING
    visits = ProviderRepository(db).visits(provider.id)
    assert len(visits) == 1 and visits[0].start_date == day
    identity, location = visits[0].id, dict(visits[0].location)
    denied = client.patch("/api/v1/provider/portal/profile", headers=owner, json={"doctor_availability": "ONGOING"})
    assert denied.status_code == 422 and "recorded" in denied.text
    cleared = client.patch("/api/v1/provider/portal/profile", headers=owner, json={
        "first_name": None, "last_name": None, "language_ids": [], "website": "https://changed.test",
    })
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["profile_update"] is None
    reloaded = client.get("/api/v1/provider/portal/profile", headers=owner).json()
    assert reloaded["editable_profile"]["language_ids"] == []
    assert reloaded["editable_profile"]["first_name"] is None
    assert reloaded["doctor_visits"][0]["id"] == str(identity)
    assert reloaded["doctor_visits"][0]["location"] == location
    db.refresh(user)
    assert user.email == "editing@example.com"
    assert client.post("/api/v1/auth/login", json={"email": user.email, "password": "ProviderPass9"}).status_code == 200


def test_invalid_owned_fields_and_explicit_proposal_resolution(client, db, seeded_admin):
    admin, _ = seeded_admin
    provider, user = _portal_doctor(db, admin, email="invalid-edit@example.com",
        publication_status=PublicationStatus.PUBLISHED)
    inactive = Language(name="Not retained", code="sz", is_active=False)
    db.add(inactive)
    db.commit()
    owner = headers(client, user)
    for body in [
        {"language_ids": [str(inactive.id)]}, {"first_name": "Only"},
        {"owner_user_id": str(admin.id)}, {"doctor_availability": "UNKNOWN"},
        {"language_ids": None},
    ]:
        response = client.patch("/api/v1/provider/portal/profile", headers=owner, json=body)
        assert response.status_code == 422, response.text
    day = date.today() + timedelta(days=6)
    assert client.patch("/api/v1/provider/portal/profile", headers=owner, json={
        "doctor_availability": "VISITING", "visit_additions": [_visit_addition(day, day)]
    }).status_code == 200
    assert client.patch("/api/v1/provider/portal/profile", headers=owner, json={"doctor_availability": "ONGOING"}).status_code == 422
    resolved = client.patch("/api/v1/provider/portal/profile", headers=owner, json={"doctor_availability": "ONGOING", "visit_additions": []})
    assert resolved.status_code == 422, resolved.text  # saved trip history is immutable
    assert client.post("/api/v1/provider/portal/profile-update/discard", headers=owner).status_code == 409
    db.refresh(provider)
    assert provider.doctor_availability == DoctorAvailability.VISITING


@pytest.mark.parametrize("provider_type", [ProviderType.CLINIC, ProviderType.HOSPITAL])
def test_clinic_languages_not_doctor_controls(client, db, seeded_admin, provider_type):
    provider, user = _portal_provider(db, seeded_admin[0], email="clinic-edit@example.com",
        name="Clinic editing", publication_status=PublicationStatus.UNPUBLISHED)
    language = Language(name="Clinic language", code="cl", is_active=True)
    provider.provider_type = provider_type
    db.add(language)
    db.commit()
    owner = headers(client, user)
    for body in [{"doctor_availability": "VISITING"}, {"first_name": "No"}, {"last_name": "No"}]:
        assert client.patch("/api/v1/provider/portal/profile", headers=owner, json=body).status_code == 422
    saved = client.patch("/api/v1/provider/portal/profile", headers=owner, json={"language_ids": [str(language.id)]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["editable_profile"]["language_ids"] == [str(language.id)]


def test_classification_approval_conflict_does_not_apply_names_or_languages(client, db, seeded_admin):
    admin, password = seeded_admin
    provider, user = _portal_doctor(db, admin, email="conflict-edit@example.com",
        publication_status=PublicationStatus.PUBLISHED)
    language = Language(name="Unapplied language", code="ul", is_active=True)
    db.add(language)
    db.commit()
    owner = headers(client, user)
    day = date.today() + timedelta(days=15)
    request = _legacy_draft(client, db, provider, headers=owner, json={
        "doctor_availability": "VISITING", "first_name": "Proposed", "last_name": "Doctor",
        "language_ids": [str(language.id)],
        "visit_additions": [_visit_addition(day, day)],
    })
    assert request.status_code == 200, request.text
    original_name = provider.name
    # A concurrent schedule write invalidates approval. Trip identity/location
    # snapshots are deliberately outside the editable-profile conflict snapshot.
    trip = DoctorVisit(provider_id=provider.id, start_date=day, end_date=day,
        location={"address_line_1": "Concurrent road", "city": "Dubai"})
    db.add(trip)
    db.commit()
    approval = client.post(
        f"/api/v1/admin/provider-profile-updates/{request.json()['profile_update']['id']}/approve",
        headers=headers(client, admin, password))
    assert approval.status_code == 409, approval.text
    db.refresh(provider)
    assert provider.name == original_name
    assert provider.doctor_availability is None
    assert provider.doctor_profile.first_name is None
    assert provider.doctor_profile.last_name is None
    assert provider.provider_languages == []
    assert db.query(DoctorVisit).filter_by(provider_id=provider.id).count() == 1


@pytest.mark.parametrize("image_format,media_type", [
    ("JPEG", "image/jpeg"), ("PNG", "image/png"), ("GIF", "image/gif"), ("WEBP", "image/webp"),
])
def test_uploaded_image_decodes_from_real_static_url(client, db, seeded_admin, tmp_path, monkeypatch, image_format, media_type):
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(portal_module, "_UPLOADS_DIR", root)
    mount = next(route for route in app.routes if getattr(route, "path", None) == "/uploads")
    monkeypatch.setattr(mount.app, "directory", str(root))
    monkeypatch.setattr(mount.app, "all_directories", [str(root)])
    _, user = _portal_provider(db, seeded_admin[0], email="decode@example.com",
        name="Image decoding fixture", publication_status=PublicationStatus.UNPUBLISHED)
    image = BytesIO()
    Image.new("RGB", (3, 2), "white").save(image, format=image_format)
    response = client.post("/api/v1/provider/portal/profile/photos/upload", headers=headers(client, user),
        files={"file": ("fixture", image.getvalue(), media_type)})
    assert response.status_code == 201, response.text
    served = client.get(response.json()["storage_reference"])
    assert served.status_code == 200
    assert served.headers["content-type"] == media_type
    with Image.open(BytesIO(served.content)) as decoded:
        decoded.load()
        assert decoded.size == (3, 2) and decoded.format == image_format
    missing = client.get("/uploads/providers/no-such-fixture.png")
    assert missing.status_code == 404
    assert missing.headers["content-type"] != "text/html"
