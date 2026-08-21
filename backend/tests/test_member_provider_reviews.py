"""Provider discovery, member reviews, and administrator moderation coverage."""
from datetime import datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.core.security import create_access_token, hash_password
from app.repositories.review_repository import ReviewRepository
from tests.conftest import TestingSessionLocal
from app.models.audit_log import AuditLog
from app.models.enums import ProviderStatus, ProviderType, PublicationStatus, VisitStability
from app.models.provider import Provider, ProviderLocation, ProviderPhoto, ProviderReview
from app.repositories.user_repository import UserRepository

MEMBER_BASE = "/api/v1/member/providers"
ADMIN_BASE = "/api/v1/admin/reviews"


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _member(db, email: str):
    repo = UserRepository(db)
    role = repo.get_role_by_name("horse_owner") or repo.create_role("horse_owner")
    user = repo.create_user(
        email=email,
        password_hash=hash_password("MemberPassword1"),
        role=role,
        roles=[role],
        first_name=email.split("@")[0].title(),
        last_name="Member",
    )
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _provider(
    db,
    name: str,
    *,
    provider_type=ProviderType.CLINIC,
    status=ProviderStatus.ACTIVE,
    publication=PublicationStatus.PUBLISHED,
    latitude: str | None = "30.267200",
    longitude: str | None = "-97.743100",
):
    provider = Provider(
        provider_type=provider_type,
        name=name,
        visit_stability=VisitStability.STABLE_VISIT,
        status=status,
        publication_status=publication,
        description=f"{name} description",
    )
    db.add(provider)
    db.flush()
    if latitude is not None and longitude is not None:
        db.add(
            ProviderLocation(
                provider_id=provider.id,
                address_line_1="1 Stable Lane",
                city="Austin",
                country="United States",
                latitude=Decimal(latitude),
                longitude=Decimal(longitude),
                is_primary=True,
            )
        )
    db.commit()
    return provider


class TestMemberProviderDiscoveryAndReviews:
    def test_directory_has_member_boundary_and_only_published_active_providers(
        self, client, db, seeded_admin
    ):
        member = _member(db, "member@example.com")
        visible = _provider(db, "Visible Clinic")
        _provider(db, "Draft Clinic", publication=PublicationStatus.UNPUBLISHED)
        _provider(db, "Inactive Clinic", status=ProviderStatus.INACTIVE)

        assert client.get(MEMBER_BASE).status_code == 401
        admin, _ = seeded_admin
        assert client.get(MEMBER_BASE, headers=_headers(admin)).status_code == 403

        response = client.get(MEMBER_BASE, headers=_headers(member))
        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload["data"]] == [str(visible.id)]
        assert payload["data"][0]["review_count"] == 0
        assert payload["data"][0]["average_rating"] is None

    def test_filters_closest_order_and_unlocated_provider_fallback(self, client, db):
        member = _member(db, "sort@example.com")
        nearby = _provider(db, "Nearby Clinic", provider_type=ProviderType.CLINIC)
        far = _provider(
            db, "Far Hospital", provider_type=ProviderType.HOSPITAL,
            latitude="35.084400", longitude="-106.650400",
        )
        unlocated = _provider(db, "Unlocated Clinic", latitude=None, longitude=None)
        db.add_all([
            ProviderReview(provider_id=nearby.id, member_id=member.id, rating=5, comment="Great"),
            ProviderReview(provider_id=far.id, member_id=member.id, rating=3, comment="Fine"),
        ])
        db.commit()

        filtered = client.get(
            MEMBER_BASE,
            headers=_headers(member),
            params={"provider_type": "CLINIC", "minimum_rating": 4},
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["data"]] == [str(nearby.id)]

        closest = client.get(
            MEMBER_BASE,
            headers=_headers(member),
            params={"closest_first": "true", "latitude": 30.2672, "longitude": -97.7431},
        )
        assert closest.status_code == 200
        items = closest.json()["data"]
        assert [item["id"] for item in items] == [str(nearby.id), str(far.id), str(unlocated.id)]
        assert items[0]["distance_km"] == 0.0
        assert items[-1]["distance_km"] is None
        assert client.get(
            MEMBER_BASE, headers=_headers(member), params={"closest_first": "true"}
        ).status_code == 422

    def test_directory_uses_selected_thumbnail_and_ordered_photo_fallback(
        self, client, db
    ):
        member = _member(db, "photos@example.com")
        selected = _provider(db, "Selected Photo Clinic")
        fallback = _provider(db, "Fallback Photo Clinic")
        db.add_all(
            [
                ProviderPhoto(
                    provider_id=selected.id,
                    storage_reference="/uploads/providers/selected.jpg",
                    alt_text="Selected clinic entrance",
                    display_order=4,
                    is_thumbnail=True,
                ),
                ProviderPhoto(
                    provider_id=selected.id,
                    storage_reference="/uploads/providers/earlier.jpg",
                    alt_text="Earlier clinic photo",
                    display_order=1,
                ),
                ProviderPhoto(
                    provider_id=fallback.id,
                    storage_reference="/uploads/providers/fallback.jpg",
                    alt_text="Fallback clinic photo",
                    display_order=2,
                ),
                ProviderPhoto(
                    provider_id=fallback.id,
                    storage_reference="/uploads/providers/first.jpg",
                    alt_text=None,
                    display_order=1,
                ),
            ]
        )
        db.commit()

        response = client.get(MEMBER_BASE, headers=_headers(member))

        assert response.status_code == 200
        items = {item["name"]: item for item in response.json()["data"]}
        assert items["Selected Photo Clinic"]["thumbnail_url"] == "/uploads/providers/selected.jpg"
        assert items["Selected Photo Clinic"]["thumbnail_alt_text"] == "Selected clinic entrance"
        assert items["Fallback Photo Clinic"]["thumbnail_url"] == "/uploads/providers/first.jpg"
        assert items["Fallback Photo Clinic"]["thumbnail_alt_text"] is None

    def test_member_can_upsert_one_review_and_hidden_comments_are_not_public(
        self, client, db, seeded_admin
    ):
        reviewer = _member(db, "reviewer@example.com")
        provider = _provider(db, "Review Clinic")
        headers = _headers(reviewer)

        created = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 4, "comment": "Caring team"},
        )
        assert created.status_code == 200
        updated = client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 5, "comment": "Even better on our second visit"},
        )
        assert updated.status_code == 200
        assert db.query(ProviderReview).count() == 1
        assert db.query(ProviderReview).one().rating == 5
        assert client.put(
            f"{MEMBER_BASE}/{provider.id}/review",
            headers=headers,
            json={"rating": 6, "comment": "Nope"},
        ).status_code == 422

        detail = client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["review_count"] == 1
        assert detail.json()["average_rating"] == 5.0
        assert detail.json()["visible_reviews"][0]["comment"] == "Even better on our second visit"

        admin, _ = seeded_admin
        review_id = updated.json()["id"]
        denied = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=headers,
            json={"comment_visible": False},
        )
        assert denied.status_code == 403
        hidden = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": False},
        )
        assert hidden.status_code == 200
        assert hidden.json()["comment_visible"] is False
        assert hidden.json()["comment"] == "Even better on our second visit"

        after_hide = client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()
        assert after_hide["review_count"] == 1
        assert after_hide["average_rating"] == 5.0
        assert after_hide["visible_reviews"] == []
        assert after_hide["own_review"]["comment"] == ""
        moderation = client.get(
            ADMIN_BASE, headers=_headers(admin), params={"comment_visible": "false"}
        )
        assert moderation.status_code == 200
        assert moderation.json()["data"][0]["id"] == review_id

        restored = client.patch(
            f"{ADMIN_BASE}/{review_id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": True},
        )
        assert restored.status_code == 200
        assert client.get(f"{MEMBER_BASE}/{provider.id}", headers=headers).json()["visible_reviews"][0]["comment"]

        events = db.query(AuditLog).filter(AuditLog.resource_id == review_id).all()
        assert events
        assert all("Caring team" not in str(event.event_metadata) for event in events)

    def test_reviews_cannot_target_an_undiscoverable_provider(self, client, db):
        member = _member(db, "missing@example.com")
        unavailable = _provider(db, "Unpublished Clinic", publication=PublicationStatus.UNPUBLISHED)
        response = client.put(
            f"{MEMBER_BASE}/{unavailable.id}/review",
            headers=_headers(member),
            json={"rating": 4, "comment": "Cannot submit"},
        )
        assert response.status_code == 404

    def test_simultaneous_first_reviews_use_one_atomic_upsert(self, db):
        member = _member(db, "concurrent@example.com")
        provider = _provider(db, "Concurrent Clinic")
        provider_id = provider.id
        member_id = member.id
        barrier = Barrier(2)

        def submit(rating: int):
            session = TestingSessionLocal()
            try:
                barrier.wait(timeout=5)
                review, _ = ReviewRepository(session).save_member_review(
                    provider_id, member_id, rating=rating, comment=f"Rating {rating}"
                )
                session.commit()
                return review.id
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            review_ids = list(pool.map(submit, [4, 5]))

        assert review_ids[0] == review_ids[1]
        assert db.query(ProviderReview).count() == 1
        assert db.query(ProviderReview).one().rating in {4, 5}

    def test_admin_provider_list_summaries_include_hidden_comments(self, client, db, seeded_admin):
        admin, _ = seeded_admin
        reviewed = _provider(db, "Reviewed Clinic")
        no_reviews = _provider(db, "No Reviews Clinic")
        visible_reviewer = _member(db, "visible-summary@example.com")
        hidden_reviewer = _member(db, "hidden-summary@example.com")
        db.add_all([
            ProviderReview(
                provider_id=reviewed.id,
                member_id=visible_reviewer.id,
                rating=5,
                comment="Visible feedback",
                comment_visible=True,
            ),
            ProviderReview(
                provider_id=reviewed.id,
                member_id=hidden_reviewer.id,
                rating=3,
                comment="Hidden feedback",
                comment_visible=False,
            ),
        ])
        db.commit()

        response = client.get("/api/v1/admin/providers", headers=_headers(admin))
        assert response.status_code == 200
        providers = {item["id"]: item for item in response.json()["data"]}
        assert providers[str(reviewed.id)]["review_count"] == 2
        assert providers[str(reviewed.id)]["average_rating"] == 4.0
        assert providers[str(no_reviews.id)]["review_count"] == 0
        assert providers[str(no_reviews.id)]["average_rating"] is None

    def test_admin_reviews_can_be_scoped_to_a_provider_and_moderated(
        self, client, db, seeded_admin
    ):
        admin, _ = seeded_admin
        provider = _provider(db, "Scoped Clinic")
        other_provider = _provider(db, "Other Clinic")
        first_reviewer = _member(db, "first-scoped@example.com")
        second_reviewer = _member(db, "second-scoped@example.com")
        other_reviewer = _member(db, "other-scoped@example.com")
        visible_review = ProviderReview(
            provider_id=provider.id,
            member_id=first_reviewer.id,
            rating=5,
            comment="Visible scoped comment",
            comment_visible=True,
        )
        hidden_review = ProviderReview(
            provider_id=provider.id,
            member_id=second_reviewer.id,
            rating=2,
            comment="Hidden scoped comment",
            comment_visible=False,
        )
        db.add_all([
            visible_review,
            hidden_review,
            ProviderReview(
                provider_id=other_provider.id,
                member_id=other_reviewer.id,
                rating=4,
                comment="Other provider comment",
            ),
        ])
        db.commit()

        params = {"provider_id": str(provider.id), "page": 1, "page_size": 1}
        assert client.get(ADMIN_BASE, params=params).status_code == 401
        assert client.get(ADMIN_BASE, headers=_headers(first_reviewer), params=params).status_code == 403

        first_page = client.get(ADMIN_BASE, headers=_headers(admin), params=params)
        assert first_page.status_code == 200
        assert first_page.json()["meta"] == {
            "page": 1,
            "page_size": 1,
            "total": 2,
            "total_pages": 2,
        }
        assert first_page.json()["data"][0]["provider_id"] == str(provider.id)
        second_page = client.get(
            ADMIN_BASE,
            headers=_headers(admin),
            params={**params, "page": 2},
        )
        assert second_page.json()["data"][0]["provider_id"] == str(provider.id)

        hidden_only = client.get(
            ADMIN_BASE,
            headers=_headers(admin),
            params={"provider_id": str(provider.id), "comment_visible": "false"},
        )
        assert hidden_only.json()["meta"]["total"] == 1
        assert hidden_only.json()["data"][0]["id"] == str(hidden_review.id)

        updated = client.patch(
            f"{ADMIN_BASE}/{visible_review.id}/comment-visibility",
            headers=_headers(admin),
            json={"comment_visible": False},
        )
        assert updated.status_code == 200
        assert updated.json()["rating"] == 5
        assert updated.json()["comment_visible"] is False
        db.refresh(visible_review)
        assert visible_review.rating == 5
