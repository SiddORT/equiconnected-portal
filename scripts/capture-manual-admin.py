#!/usr/bin/env python3
"""Capture real admin UI screens with isolated, browser-only sample fixtures.

All /api/v1 requests are fulfilled by this script before they can reach the
application server. No login, database, email service, or backend writes are
used. The visible sample-data banner is installed before each page loads.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "frontend" / "public" / "manual"
DOC_PATH = ROOT / "docs" / "manual-admin-screenshots.md"
MAPPING_PATH = ROOT / "frontend" / "src" / "pages" / "admin" / "manual" / "adminScreenshots.ts"
CDP_PORT = 9241
WIDTH = 1680
HEIGHT = 1080
TODAY = "2026-10-01"
STAMP = "2026-10-01T10:30:00Z"
FUTURE_START = "2026-10-15"
FUTURE_END = "2026-10-18"


def sample_photo(filename: str) -> str:
    return f"/uploads/providers/sample-doctor/photos/{filename}"


def stamp(days: int = 0) -> str:
    return f"2026-10-{max(1, 1 + days):02d}T10:30:00Z"


def paged(rows: list[dict[str, Any]], query: dict[str, list[str]]) -> dict[str, Any]:
    try:
        page = max(1, int(query.get("page", ["1"])[0]))
        page_size = max(1, min(100, int(query.get("page_size", ["25"])[0])))
    except ValueError:
        page, page_size = 1, 25
    start = (page - 1) * page_size
    sliced = rows[start : start + page_size]
    total_pages = max(1, (len(rows) + page_size - 1) // page_size)
    return {
        "data": sliced,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": len(rows),
            "total_pages": total_pages,
        },
    }


SPECS = [
    {"id": "sample-spec-equine", "name": "Sample Equine Medicine", "description": "Sample specialization fixture.", "is_active": True, "created_at": STAMP, "updated_at": STAMP},
    {"id": "sample-spec-surgery", "name": "Sample Equine Surgery", "description": "Sample specialization fixture.", "is_active": True, "created_at": STAMP, "updated_at": STAMP},
    {"id": "sample-spec-dentistry", "name": "Sample Veterinary Dentistry", "description": "Sample specialization fixture.", "is_active": True, "created_at": STAMP, "updated_at": STAMP},
]
LANGUAGES = [
    {"id": "sample-language-en", "name": "Sample English", "code": "en", "is_active": True, "created_at": STAMP, "updated_at": STAMP},
    {"id": "sample-language-fr", "name": "Sample French", "code": "fr", "is_active": True, "created_at": STAMP, "updated_at": STAMP},
]

LOCATION = {
    "id": "sample-location-primary",
    "provider_id": "sample-doctor",
    "name": "Sample Main Office",
    "address_line_1": "100 Sample Lane",
    "address_line_2": None,
    "city": "Sample Harbor",
    "state_province": "Sample State",
    "country": "Sample Country",
    "postal_code": "00000",
    "latitude": None,
    "longitude": None,
    "is_primary": True,
}
SECONDARY_LOCATION = {
    "id": "sample-location-visit",
    "provider_id": "sample-doctor",
    "name": "Sample Visiting Centre",
    "address_line_1": "200 Demonstration Road",
    "address_line_2": None,
    "city": "Sample Foothills",
    "state_province": "Sample State",
    "country": "Sample Country",
    "postal_code": "00001",
    "latitude": None,
    "longitude": None,
    "is_primary": False,
}

DOCTOR = {
    "id": "sample-doctor",
    "provider_type": "DOCTOR",
    "name": "Sample Dr. Avery Field",
    "description": "Sample mobile equine care profile for manual demonstrations.",
    "website": "https://sample-provider.example.test",
    "email": "sample.avery@example.test",
    "phone": "+1 555 010 0101",
    "status": "ACTIVE",
    "publication_status": "UNPUBLISHED",
    "visit_stability": "STABLE_VISIT",
    "maximum_working_radius_km": 32,
    "emergency_services_available": True,
    "emergency_contact_name": "Sample on-call contact",
    "emergency_contact_number": "+1 555 010 0199",
    "years_experience": 12,
    "specializations": [SPECS[0], SPECS[1]],
    "specialization_count": 2,
    "languages": LANGUAGES,
    "locations": [LOCATION, SECONDARY_LOCATION],
    "phones": [
        {"id": "sample-phone-primary", "provider_id": "sample-doctor", "country_code": "+1", "number": "555 010 0101", "is_primary": True},
        {"id": "sample-phone-office", "provider_id": "sample-doctor", "country_code": "+1", "number": "555 010 0102", "is_primary": False},
    ],
    "emails": [
        {"id": "sample-email-primary", "provider_id": "sample-doctor", "email": "sample.avery@example.test", "is_primary": True},
        {"id": "sample-email-office", "provider_id": "sample-doctor", "email": "sample.office@example.test", "is_primary": False},
    ],
    "doctor_profile": {
        "id": "sample-doctor-profile",
        "provider_id": "sample-doctor",
        "first_name": "Sample Avery",
        "last_name": "Field",
        "professional_title": "Sample Equine Veterinarian",
        "years_experience": 12,
        "biography": "Sample professional biography for demonstration only.",
        "experience_description": "Sample experience notes for demonstration only.",
    },
    "doctor_availability": "VISITING",
    "can_schedule_visits": True,
    "doctor_visits": [
        {
            "id": "sample-visit-upcoming",
            "provider_id": "sample-doctor",
            "start_date": FUTURE_START,
            "end_date": FUTURE_END,
            "location": {
                "name": "Sample Autumn Visit",
                "address_line_1": "200 Demonstration Road",
                "city": "Sample Foothills",
                "state_province": "Sample State",
                "country": "Sample Country",
                "postal_code": "00001",
            },
            "created_at": STAMP,
            "updated_at": STAMP,
        },
        {
            "id": "sample-visit-past",
            "provider_id": "sample-doctor",
            "start_date": "2026-09-02",
            "end_date": "2026-09-07",
            "location": {
                "name": "Sample Summer Visit",
                "address_line_1": "300 Sample Trail",
                "city": "Sample Meadow",
                "state_province": "Sample State",
                "country": "Sample Country",
                "postal_code": "00002",
            },
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    ],
    "qualifications": [
        {"id": "sample-qualification-1", "provider_id": "sample-doctor", "title": "Sample DVM", "institution": "Sample Veterinary College", "year_obtained": 2014, "description": "Sample qualification record.", "display_order": 0, "created_at": STAMP, "updated_at": STAMP},
        {"id": "sample-qualification-2", "provider_id": "sample-doctor", "title": "Sample Equine Practice Certificate", "institution": "Sample Learning Centre", "year_obtained": 2018, "description": None, "display_order": 1, "created_at": STAMP, "updated_at": STAMP},
    ],
    "average_rating": 4.7,
    "review_count": 8,
    "visible_reviews": [],
    "thumbnail_url": sample_photo("horse-panel.jpg"),
    "photos": [
        {
            "id": "sample-photo-current",
            "provider_id": "sample-doctor",
            "storage_reference": sample_photo("horse-panel.jpg"),
            "alt_text": "Sample horse in an open paddock",
            "caption": "Sample current profile photo",
            "display_order": 0,
            "is_thumbnail": True,
            "created_at": STAMP,
            "updated_at": STAMP,
        },
        {
            "id": "sample-photo-gallery",
            "provider_id": "sample-doctor",
            "storage_reference": sample_photo("stable-panel.jpg"),
            "alt_text": "Sample unmarked stable exterior",
            "caption": "Sample provider gallery photo",
            "display_order": 1,
            "is_thumbnail": False,
            "created_at": STAMP,
            "updated_at": STAMP,
        },
    ],
    "created_at": STAMP,
    "updated_at": STAMP,
    "doctor_fields_available": True,
    "profile_update": {
        "id": "sample-profile-update",
        "review_status": "PENDING_REVIEW",
        "submitted_at": STAMP,
        "reviewed_at": None,
        "reviewed_by_name": None,
        "rejection_reason": None,
    },
}
DOCTOR["editable_profile"] = {
    "name": DOCTOR["name"],
    "description": DOCTOR["description"],
    "email": DOCTOR["email"],
    "phone": DOCTOR["phone"],
    "website": DOCTOR["website"],
    "visit_stability": DOCTOR["visit_stability"],
    "maximum_working_radius_km": DOCTOR["maximum_working_radius_km"],
    "emergency_services_available": True,
    "emergency_contact_number": DOCTOR["emergency_contact_number"],
    "specialization_ids": [SPECS[0]["id"], SPECS[1]["id"]],
    "locations": [{k: v for k, v in LOCATION.items() if k not in ("id", "provider_id")}],
    "phones": [{"country_code": "+1", "number": "555 010 0101", "is_primary": True}],
    "emails": [{"email": "sample.avery@example.test", "is_primary": True}],
    "photos": [],
    "visit_additions": [],
    "professional_title": "Sample Equine Veterinarian",
    "biography": "Sample professional biography for demonstration only.",
    "experience_description": "Sample experience notes for demonstration only.",
    "years_experience": 12,
    "qualifications": [
        {"title": "Sample DVM", "institution": "Sample Veterinary College", "year_obtained": 2014, "description": "Sample qualification record.", "display_order": 0},
    ],
}

CLINIC = {
    **DOCTOR,
    "id": "sample-clinic",
    "provider_type": "CLINIC",
    "name": "Sample Meadow Equine Clinic",
    "description": "Sample clinic record used to illustrate independent status and publication controls.",
    "email": "sample.clinic@example.test",
    "phone": "+1 555 010 0201",
    "status": "ACTIVE",
    "publication_status": "PUBLISHED",
    "visit_stability": "STABLE_VISIT",
    "doctor_profile": None,
    "doctor_availability": None,
    "doctor_visits": [],
    "doctor_fields_available": False,
    "qualifications": [],
    "profile_update": None,
    "thumbnail_url": sample_photo("stable-panel.jpg"),
}
CLINIC["specializations"] = [SPECS[0], SPECS[2]]
CLINIC["specialization_count"] = 2
CLINIC["emails"] = [
    {"id": "sample-clinic-email", "provider_id": "sample-clinic", "email": "sample.clinic@example.test", "is_primary": True},
]
CLINIC["phones"] = [
    {"id": "sample-clinic-phone", "provider_id": "sample-clinic", "country_code": "+1", "number": "555 010 0201", "is_primary": True},
]
CLINIC["locations"] = [{**LOCATION, "id": "sample-clinic-location", "provider_id": "sample-clinic"}]
CLINIC["editable_profile"] = {
    **DOCTOR["editable_profile"],
    "name": CLINIC["name"],
    "description": CLINIC["description"],
    "email": CLINIC["email"],
    "phone": CLINIC["phone"],
    "specialization_ids": [SPECS[0]["id"], SPECS[2]["id"]],
    "photos": [],
}

PROVIDER_ROWS = [
    {
        "id": "sample-clinic",
        "name": "Sample Meadow Equine Clinic",
        "provider_type": "CLINIC",
        "email": "sample.clinic@example.test",
        "phone": "+1 555 010 0201",
        "visit_stability": "STABLE_VISIT",
        "emergency_services_available": True,
        "average_rating": 4.8,
        "review_count": 12,
        "status": "ACTIVE",
        "publication_status": "PUBLISHED",
        "created_at": STAMP,
        "updated_at": STAMP,
        "thumbnail_url": sample_photo("stable-panel.jpg"),
    },
    {
        "id": "sample-doctor",
        "name": "Sample Dr. Avery Field",
        "provider_type": "DOCTOR",
        "email": "sample.avery@example.test",
        "phone": "+1 555 010 0101",
        "visit_stability": "STABLE_VISIT",
        "emergency_services_available": True,
        "average_rating": 4.7,
        "review_count": 8,
        "status": "ACTIVE",
        "publication_status": "UNPUBLISHED",
        "created_at": STAMP,
        "updated_at": STAMP,
        "thumbnail_url": sample_photo("horse-panel.jpg"),
    },
    {
        "id": "sample-hospital",
        "name": "Sample Coastal Veterinary Hospital",
        "provider_type": "HOSPITAL",
        "email": "sample.hospital@example.test",
        "phone": "+1 555 010 0301",
        "visit_stability": "NOT_STABLE_VISIT",
        "emergency_services_available": False,
        "average_rating": 4.3,
        "review_count": 5,
        "status": "INACTIVE",
        "publication_status": "UNPUBLISHED",
        "created_at": STAMP,
        "updated_at": STAMP,
        "thumbnail_url": None,
    },
]

USERS = [
    {
        "id": "sample-user-owner",
        "first_name": "Sample Taylor",
        "last_name": "Owner",
            "full_name": "Sample Taylor Owner",
        "email": "sample.owner@example.test",
            "mobile_number": "+1 555 010 0401",
        "country": "Sample Country",
        "city": "Sample Harbor",
        "roles": ["horse_owner"],
        "email_verified_at": STAMP,
        "created_at": STAMP,
    },
    {
        "id": "sample-user-manager",
        "first_name": "Sample Jordan",
        "last_name": "Manager",
            "full_name": "Sample Jordan Manager",
        "email": "sample.manager@example.test",
            "mobile_number": "+1 555 010 0402",
        "country": "Sample Country",
        "city": "Sample Meadow",
        "roles": ["stable_manager"],
        "email_verified_at": None,
        "created_at": STAMP,
    },
]

APPLICATION = {
    "id": "sample-application",
    "user_id": "sample-user-applicant",
    "provider_id": None,
    "provider_type": "DOCTOR",
    "provider_name": "Sample Dr. Morgan Vale",
    "first_name": "Sample Morgan",
    "last_name": "Vale",
    "contact_name": "Sample Morgan Vale",
    "full_name": "Sample Morgan Vale",
    "email": "sample.applicant@example.test",
    "phone": "+1 555 010 0501",
    "mobile_number": "+1 555 010 0501",
    "website": "https://sample-applicant.example.test",
    "status": "PENDING_REVIEW",
    "review_status": "PENDING_REVIEW",
    "email_verified": True,
    "email_verified_at": STAMP,
    "created_at": STAMP,
    "submitted_at": STAMP,
    "reviewed_at": None,
    "reviewed_by_name": None,
    "rejection_reason": None,
    "biography": "Sample application biography for demonstration only.",
    "experience_description": "Sample application experience notes.",
    "professional_title": "Sample Visiting Equine Veterinarian",
    "years_experience": 10,
    "specializations": [SPECS[0]],
    "languages": LANGUAGES[:1],
    "locations": [{k: v for k, v in LOCATION.items() if k != "id"}],
    "emails": [{"email": "sample.applicant@example.test", "is_primary": True}],
    "phones": [{"country_code": "+1", "number": "555 010 0501", "is_primary": True}],
    "visit_stability": "STABLE_VISIT",
    "maximum_working_radius_km": 24,
    "emergency_services_available": False,
    "emergency_contact_number": None,
    "doctor_availability": "VISITING",
    "doctor_visits": [],
    "qualifications": [
        {"title": "Sample DVM", "institution": "Sample Veterinary College", "year_obtained": 2016, "description": "Sample application qualification.", "display_order": 0},
    ],
    "consent_given": True,
    "consent_at": STAMP,
    "terms_accepted_at": STAMP,
    "privacy_accepted_at": STAMP,
    "specialization_ids": ["sample-spec-equine"],
    "postal_code": "00000",
    "stable_visit": True,
    "country": "Sample Country",
    "state_province": "Sample State",
    "city": "Sample Harbor",
    "reviewed_by_user_id": None,
    "created_provider_id": None,
    "created_provider_name": None,
    "decision_available": True,
}

PROFILE_UPDATE = {
    "id": "sample-profile-update",
    "provider_id": "sample-doctor",
    "provider_name": "Sample Dr. Avery Field",
    "provider_type": "DOCTOR",
    "review_status": "PENDING_REVIEW",
    "status": "PENDING_REVIEW",
    "submitted_at": STAMP,
    "reviewed_at": None,
    "reviewed_by_name": None,
    "rejection_reason": None,
    "reviewed_by_user_id": None,
    "provider": DOCTOR,
    "current_profile": {
        "name": "Sample Dr. Avery Field",
        "description": "Sample mobile equine care profile for manual demonstrations.",
        "email": "sample.avery@example.test",
        "phone": "+1 555 010 0101",
        "website": "https://sample-provider.example.test",
        "visit_stability": "STABLE_VISIT",
        "maximum_working_radius_km": 32,
        "emergency_services_available": True,
        "emergency_contact_number": "+1 555 010 0199",
        "specializations": [SPECS[0]],
        "specialization_ids": [SPECS[0]["id"]],
        "locations": [LOCATION],
        "emails": DOCTOR["emails"],
        "phones": DOCTOR["phones"],
        "doctor_profile": DOCTOR["doctor_profile"],
        "qualifications": DOCTOR["qualifications"],
        "photos": [
            {
                "id": "sample-photo-current",
                "storage_reference": sample_photo("horse-panel.jpg"),
                "alt_text": "Sample horse in an open paddock",
                "caption": "Sample current profile photo",
                "is_thumbnail": True,
                "display_order": 0,
            }
        ],
        "doctor_visits": DOCTOR["doctor_visits"],
    },
    "proposed_profile": {
        "name": "Sample Dr. Avery Field",
        "description": "Sample profile update with revised mobile-care overview.",
        "email": "sample.avery@example.test",
        "phone": "+1 555 010 0101",
        "website": "https://sample-updated-provider.example.test",
        "visit_stability": "STABLE_VISIT",
        "maximum_working_radius_km": 40,
        "emergency_services_available": True,
        "emergency_contact_number": "+1 555 010 0199",
        "specializations": [SPECS[0], SPECS[1]],
        "specialization_ids": [SPECS[0]["id"], SPECS[1]["id"]],
        "locations": [LOCATION, SECONDARY_LOCATION],
        "emails": DOCTOR["emails"],
        "phones": DOCTOR["phones"],
        "doctor_profile": {
            **DOCTOR["doctor_profile"],
            "biography": "Sample revised biography in the proposed update.",
        },
        "qualifications": [
            *DOCTOR["qualifications"],
            {"id": "sample-qualification-proposed", "title": "Sample Advanced Equine Certificate", "institution": "Sample Learning Centre", "year_obtained": 2024, "description": "Sample proposed qualification.", "display_order": 2},
        ],
        "photos": [
            {
                "id": "sample-photo-current",
                "storage_reference": sample_photo("horse-panel.jpg"),
                "alt_text": "Sample horse in an open paddock",
                "caption": "Sample current profile photo",
                "is_thumbnail": False,
                "display_order": 0,
            },
            {
                "id": "sample-photo-proposed",
                "storage_reference": sample_photo("stable-panel.jpg"),
                "alt_text": "Sample unmarked stable exterior",
                "caption": "Sample proposed gallery photo",
                "is_thumbnail": True,
                "display_order": 1,
            },
        ],
        "doctor_visits": DOCTOR["doctor_visits"],
    },
    "current_photos": [
        {
            "id": "sample-photo-current",
            "storage_reference": sample_photo("horse-panel.jpg"),
            "alt_text": "Sample horse in an open paddock",
            "caption": "Sample current profile photo",
            "is_thumbnail": True,
            "display_order": 0,
        }
    ],
    "proposed_photos": [
        {
            "id": "sample-photo-current",
            "storage_reference": sample_photo("horse-panel.jpg"),
            "alt_text": "Sample horse in an open paddock",
            "caption": "Sample current profile photo",
            "is_thumbnail": False,
            "display_order": 0,
            "change_type": "UNCHANGED",
        },
        {
            "id": "sample-photo-proposed",
            "storage_reference": sample_photo("stable-panel.jpg"),
            "alt_text": "Sample unmarked stable exterior",
            "caption": "Sample proposed gallery photo",
            "is_thumbnail": True,
            "display_order": 1,
            "change_type": "ADDED",
        },
    ],
    "created_at": STAMP,
    "photo_changes": [
        {"change_type": "UNCHANGED", "photo_id": "sample-photo-current"},
        {"change_type": "ADDED", "photo_id": "sample-photo-proposed"},
    ],
}

INVITATIONS = [
    {"id": "sample-invitation-pending", "recipient_email": "sample.pending@example.test", "provider_type": "CLINIC", "provider_name": "Sample Pending Clinic", "status": "PENDING", "sent_at": STAMP, "expires_at": "2026-11-01T10:30:00Z", "accepted_at": None, "completed_at": None, "portal_access_created_at": None},
    {"id": "sample-invitation-accepted", "recipient_email": "sample.accepted@example.test", "provider_type": "HOSPITAL", "provider_name": "Sample Accepted Hospital", "status": "ACCEPTED", "sent_at": STAMP, "expires_at": "2026-11-01T10:30:00Z", "accepted_at": STAMP, "completed_at": None, "portal_access_created_at": None},
    {"id": "sample-invitation-expired", "recipient_email": "sample.expired@example.test", "provider_type": "DOCTOR", "provider_name": "Sample Expired Doctor", "status": "EXPIRED", "sent_at": STAMP, "expires_at": "2026-09-01T10:30:00Z", "accepted_at": None, "completed_at": None, "portal_access_created_at": None},
    {"id": "sample-invitation-cancelled", "recipient_email": "sample.cancelled@example.test", "provider_type": "CLINIC", "provider_name": "Sample Cancelled Clinic", "status": "CANCELLED", "sent_at": STAMP, "expires_at": "2026-11-01T10:30:00Z", "accepted_at": None, "completed_at": None, "portal_access_created_at": None},
    {"id": "sample-invitation-completed", "recipient_email": "sample.completed@example.test", "provider_type": "DOCTOR", "provider_name": "Sample Dr. Completed Vale", "status": "COMPLETED", "sent_at": STAMP, "expires_at": "2026-11-01T10:30:00Z", "accepted_at": STAMP, "completed_at": STAMP, "portal_access_created_at": STAMP},
]

REVIEW = {
    "id": "sample-review",
    "provider_id": "sample-clinic",
    "provider_name": "Sample Meadow Equine Clinic",
    "reviewer_id": "sample-user-owner",
    "reviewer_name": "Sample Taylor Owner",
    "reviewer_email": "sample.owner@example.test",
    "rating": 4,
    "comment": "Sample review fixture: clear communication during a demonstration visit.",
    "status": "PENDING",
    "comment_visible": False,
    "member_note": None,
    "internal_note": None,
    "version": 1,
    "deleted_at": None,
    "created_at": STAMP,
    "updated_at": STAMP,
    "history": [
        {
            "id": "sample-review-history",
            "actor_id": None,
            "actor_name": None,
            "actor_email": "",
            "actor_type": "system",
            "action": "submitted",
            "from_status": None,
            "to_status": "PENDING",
            "version": 1,
            "content_snapshot": {
                "rating": 4,
                "comment": "Sample review fixture: clear communication during a demonstration visit.",
            },
            "created_at": STAMP,
        },
    ],
}

CONTACT = {
    "id": "sample-contact-enquiry",
    "name": "Sample Riley Contact",
    "email": "sample.contact@example.test",
    "enquiry_type": "general",
    "message": "Sample demonstration message: please share general information about provider onboarding.",
    "phone": "+1 555 010 0601",
    "submitted_at": STAMP,
}
FEEDBACK = {
    "id": "sample-feedback",
    "member_id": "sample-user-owner",
    "submitter_name": "Sample Quinn Feedback",
    "submitter_email": "sample.feedback@example.test",
    "category": "Website / App",
    "subject": "Sample feedback on directory navigation",
    "rating": 4,
    "message": "Sample demonstration feedback: the directory controls are easy to find.",
    "status": "Pending",
    "withdrawn_at": None,
    "member_response": None,
    "internal_note": None,
    "version": 1,
    "submitted_at": STAMP,
    "updated_at": STAMP,
    "history": [
        {
            "id": "sample-feedback-submitted",
            "actor_id": "sample-user-owner",
            "actor_name": "Sample Taylor Owner",
            "actor_email": "sample.owner@example.test",
            "actor_type": "member",
            "action": "submitted",
            "from_status": None,
            "to_status": "Pending",
            "version": 1,
            "content_snapshot": {
                "subject": "Sample feedback on directory navigation",
                "category": "Website / App",
                "message": "Sample demonstration feedback: the directory controls are easy to find.",
            },
            "created_at": STAMP,
        },
    ],
}

ACTIVITY_LOGS = [
    {"id": "sample-activity-1", "action": "provider.viewed", "resource_type": "provider", "resource_id": "sample-clinic", "actor": {"id": "sample-admin", "name": "Sample Admin", "email": "sample.admin@example.test", "kind": "admin"}, "created_at": STAMP, "summary": "Sample Admin viewed Sample Meadow Equine Clinic.", "changes": [], "metadata": {"ip_address": "192.0.2.10", "sample": True}},
    {"id": "sample-activity-2", "action": "application.reviewed", "resource_type": "application", "resource_id": "sample-application", "actor": {"id": "sample-admin", "name": "Sample Admin", "email": "sample.admin@example.test", "kind": "admin"}, "created_at": STAMP, "summary": "Sample Admin reviewed Sample Dr. Morgan Vale.", "changes": [{"field": "review_status", "before": "PENDING_REVIEW", "after": "APPROVED"}], "metadata": {"ip_address": "192.0.2.11", "sample": True}},
]
EMAIL_LOGS = [
    {"id": "sample-email-log-accepted", "recipient_email": "sample.owner@example.test", "purpose": "subscriber_confirmation", "status": "success", "failure_message": None, "created_at": STAMP},
    {"id": "sample-email-log-failed", "recipient_email": "sample.office@example.test", "purpose": "provider_portal_access", "status": "failed", "failure_message": "Sample fixture delivery was not accepted.", "created_at": STAMP},
]

SUBSCRIBERS = [
    {"id": "sample-subscriber-1", "email": "sample.subscriber@example.test", "registration_type": "HORSE_OWNER", "submitted_at": STAMP},
    {"id": "sample-subscriber-2", "email": "sample.former-subscriber@example.test", "registration_type": "STABLE_MANAGER", "submitted_at": STAMP},
]


class FixtureAPI:
    def __init__(self) -> None:
        self.access_by_provider: dict[str, dict[str, Any]] = {}
        self.application_state = json.loads(json.dumps(APPLICATION))
        self.profile_update_state = json.loads(json.dumps(PROFILE_UPDATE))
        self.review_state = json.loads(json.dumps(REVIEW))
        self.contact_state = json.loads(json.dumps(CONTACT))
        self.feedback_state = json.loads(json.dumps(FEEDBACK))
        self.seen: list[str] = []
        self.unknown: list[str] = []
        self.write_requests: list[str] = []
        self.failures: list[str] = []

    def route(self, url: str, method: str, body: Any) -> tuple[int, Any]:
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.seen.append(f"{method} {path}")
        if method not in ("GET", "HEAD", "OPTIONS"):
            self.write_requests.append(f"{method} {path} (browser fixture only)")

        if path == "/api/v1/auth/refresh":
            return 200, {
                "access_token": "sample-only-admin-fixture-session",
                "token_type": "bearer",
                "user": {
                    "id": "sample-admin",
                    "email": "sample.admin@example.test",
                    "first_name": "Sample",
                    "last_name": "Admin",
                    "full_name": "Sample Admin",
                    "role": "admin",
                    "is_active": True,
                    "created_at": STAMP,
                },
            }
        if path in ("/api/v1/auth/logout", "/api/v1/auth/me"):
            return 200, {"ok": True, "user": {"id": "sample-admin", "email": "sample.admin@example.test", "role": "admin"}}
        if path == "/api/v1/auth/provider-languages":
            return 200, [{"id": item["id"], "name": item["name"].removeprefix("Sample "), "code": item["code"]} for item in LANGUAGES]
        if path in ("/api/v1/system-settings", "/api/v1/admin/system-settings") and method == "GET":
            return 200, {"timezone": "UTC", "date_format": "month_day_year", "time_format": "12_hour"}
        if path == "/api/v1/admin/system-settings" and method == "PATCH":
            payload = body if isinstance(body, dict) else {}
            return 200, {
                "timezone": payload.get("timezone", "UTC"),
                "date_format": payload.get("date_format", "month_day_year"),
                "time_format": payload.get("time_format", "12_hour"),
            }
        if path == "/api/v1/admin/dashboard/stats":
            return 200, {
                "total_providers": 3,
                "active_providers": 2,
                "pending_applications": 1,
                "pending_reviews": 1,
                "provider_counts": {"total": 3, "active": 2, "inactive": 1, "under_review": 0},
                "activity": [{"label": "Sample provider review", "count": 2}],
                "recent_activity": ACTIVITY_LOGS,
                "visiting_providers": [],
            }
        if path == "/api/v1/admin/dashboard/visits":
            visit_month = query.get("month", [TODAY[:7]])[0]
            visit_start = f"{visit_month}-15"
            visit_end = f"{visit_month}-18"
            return 200, {
                "month": visit_month,
                "today": visit_start,
                "visits": [{
                    "id": "sample-visit-upcoming",
                    "provider_id": "sample-doctor",
                    "provider_name": "Sample Dr. Avery Field",
                    "start_date": visit_start,
                    "end_date": visit_end,
                    "specializations": ["Sample Equine Medicine"],
                    "location": {
                        "name": "Sample Autumn Visit",
                        "city": "Sample Foothills",
                        "state_province": "Sample State",
                        "country": "Sample Country",
                    },
                }],
            }
        if path == "/api/v1/admin/users" and method == "GET":
            return 200, paged(USERS, query)
        if path.startswith("/api/v1/admin/users/") and method == "GET":
            return 200, USERS[0]

        if path == "/api/v1/admin/providers" and method == "GET":
            return 200, paged(PROVIDER_ROWS, query)
        provider_match = None
        if path.startswith("/api/v1/admin/providers/"):
            provider_match = path.removeprefix("/api/v1/admin/providers/").split("/")
        if provider_match:
            provider_id = provider_match[0]
            provider = DOCTOR if provider_id == "sample-doctor" else CLINIC
            suffix = provider_match[1:] if len(provider_match) > 1 else []
            if suffix == ["portal-access"] and method == "GET":
                if provider_id not in self.access_by_provider:
                    self.access_by_provider[provider_id] = {
                        "status": "eligible" if provider_id == "sample-clinic" else "active",
                        "action": "setup" if provider_id == "sample-clinic" else "reset",
                        "available": True,
                        "can_send": True,
                        "can_revoke": False,
                        "recipient_email": "sample.clinic@example.test" if provider_id == "sample-clinic" else "sample.avery@example.test",
                        "sent_at": None if provider_id == "sample-clinic" else STAMP,
                        "message": "Sample account state; no message has been delivered.",
                        "reason": None,
                        "invitation_id": None,
                        "selectable_emails": [
                            {"email_id": "sample-email-primary", "email": "sample.clinic@example.test" if provider_id == "sample-clinic" else "sample.avery@example.test", "is_primary": True}
                        ],
                    }
                return 200, self.access_by_provider[provider_id]
            if suffix == ["portal-access"] and method == "POST":
                self.access_by_provider[provider_id] = {
                    "status": "pending" if provider_id == "sample-clinic" else "active",
                    "action": "setup" if provider_id == "sample-clinic" else "reset",
                    "available": True,
                    "can_send": True,
                    "can_revoke": provider_id == "sample-clinic",
                    "recipient_email": "sample.clinic@example.test" if provider_id == "sample-clinic" else "sample.avery@example.test",
                    "sent_at": STAMP,
                    "message": "Sample request preview only. No email was sent.",
                    "reason": None,
                    "invitation_id": None,
                    "selectable_emails": [
                        {"email_id": "sample-email-primary", "email": "sample.clinic@example.test" if provider_id == "sample-clinic" else "sample.avery@example.test", "is_primary": True}
                    ],
                }
                return 200, self.access_by_provider[provider_id]
            if suffix == ["portal-access"] and method in ("DELETE", "PATCH"):
                self.access_by_provider[provider_id] = {
                    **self.access_by_provider.get(provider_id, {}),
                    "status": "eligible",
                    "can_revoke": False,
                    "message": "Sample fixture: pending access was canceled in the browser only.",
                }
                return 200, self.access_by_provider[provider_id]
            if suffix and suffix[0] in ("status", "publication", "approve", "photos", "locations", "emails", "phones", "specializations"):
                return 200, provider
            if method == "GET" and not suffix:
                return 200, provider

        if path == "/api/v1/admin/doctors" and method == "GET":
            rows = [{
                "id": "sample-doctor",
                "name": DOCTOR["name"],
                "visit_stability": "STABLE_VISIT",
                "status": "ACTIVE",
                "publication_status": "UNPUBLISHED",
                "created_at": STAMP,
                "updated_at": STAMP,
                "thumbnail_url": DOCTOR["thumbnail_url"],
                "professional_title": "Sample Equine Veterinarian",
                "specializations": [{"id": SPECS[0]["id"], "name": SPECS[0]["name"], "is_active": True}],
                "primary_organization": {"id": "sample-clinic", "provider_type": "CLINIC", "name": CLINIC["name"], "thumbnail_url": CLINIC["thumbnail_url"]},
                "organization_count": 1,
            }]
            return 200, paged(rows, query)
        if path == "/api/v1/admin/doctors/sample-doctor" and method == "GET":
            return 200, {
                "id": "sample-doctor",
                "name": DOCTOR["name"],
                "visit_stability": DOCTOR["visit_stability"],
                "status": DOCTOR["status"],
                "publication_status": DOCTOR["publication_status"],
                "website": DOCTOR["website"],
                "created_at": STAMP,
                "updated_at": STAMP,
                "thumbnail_url": DOCTOR["thumbnail_url"],
                "professional_title": "Sample Equine Veterinarian",
                "biography": DOCTOR["doctor_profile"]["biography"],
                "years_experience": 12,
                "experience_description": DOCTOR["doctor_profile"]["experience_description"],
                "specializations": [{"id": SPECS[0]["id"], "name": SPECS[0]["name"], "is_active": True}],
                "qualifications": DOCTOR["qualifications"],
                "organizations": [{
                    "id": "sample-doctor-org",
                    "organization_id": "sample-clinic",
                    "status": "ACTIVE",
                    "is_primary": True,
                    "created_at": STAMP,
                    "updated_at": STAMP,
                    "organization": {"id": "sample-clinic", "provider_type": "CLINIC", "name": CLINIC["name"], "thumbnail_url": CLINIC["thumbnail_url"]},
                }],
                "phones": DOCTOR["phones"],
                "emails": DOCTOR["emails"],
            }
        if path.startswith("/api/v1/admin/doctors/sample-doctor/qualifications"):
            if method == "POST":
                record = {**(body if isinstance(body, dict) else {}), "id": "sample-qualification-new", "provider_id": "sample-doctor", "created_at": STAMP, "updated_at": STAMP}
                return 201, record
            return 200, DOCTOR["qualifications"][0]
        if path.startswith("/api/v1/admin/doctors/sample-doctor/organizations"):
            return 200, {
                "id": "sample-doctor",
                "organizations": [{
                    "id": "sample-doctor-org",
                    "organization_id": "sample-clinic",
                    "status": "ACTIVE",
                    "is_primary": True,
                    "created_at": STAMP,
                    "updated_at": STAMP,
                    "organization": {"id": "sample-clinic", "provider_type": "CLINIC", "name": CLINIC["name"], "thumbnail_url": CLINIC["thumbnail_url"]},
                }],
            }

        if path == "/api/v1/admin/specializations" and method == "GET":
            rows = SPECS
            if query.get("is_active", [""])[0].lower() == "true":
                rows = [row for row in rows if row["is_active"]]
            if query.get("is_active", [""])[0].lower() == "false":
                rows = [row for row in rows if not row["is_active"]]
            return 200, paged(rows, query)
        if path == "/api/v1/admin/languages" and method == "GET":
            return 200, paged(LANGUAGES, query)
        if path.endswith("/specializations/import/preview") or path.endswith("/specializations/import-preview"):
            return 200, {
                "total": 3,
                "valid": 1,
                "duplicate": 1,
                "invalid": 1,
                "rows": [
                    {"row_num": 2, "name": "Sample Equine Sports Medicine", "description": "Sample valid CSV row.", "status": "ACTIVE", "state": "valid", "reason": None},
                    {"row_num": 3, "name": "Sample Equine Medicine", "description": "Sample duplicate row.", "status": "ACTIVE", "state": "duplicate", "reason": "A specialization with this name already exists."},
                    {"row_num": 4, "name": "", "description": "Sample invalid CSV row.", "status": "ACTIVE", "state": "invalid", "reason": "Name is required."},
                ],
            }
        if path.endswith("/specializations/import") or path.endswith("/specializations/import/confirm"):
            return 200, {"imported": 1, "skipped": 2, "errors": 0, "row_details": []}
        if path.endswith("/specializations/template"):
            return 200, {"ok": True}
        if path.endswith("/export") and "subscriber" not in path:
            return 200, {"ok": True}

        if path == "/api/v1/admin/provider-applications" and method == "GET":
            return 200, paged([self.application_state], query)
        if path == "/api/v1/admin/provider-applications/sample-application" and method == "GET":
            return 200, self.application_state
        if path.startswith("/api/v1/admin/provider-applications/sample-application/") and method == "POST":
            if path.endswith("/approve"):
                self.application_state = {
                    **self.application_state,
                    "status": "APPROVED",
                    "review_status": "APPROVED",
                    "reviewed_at": STAMP,
                    "reviewed_by_name": "Sample Admin",
                    "provider_id": "sample-staged-provider",
                    "created_provider_id": "sample-staged-provider",
                    "created_provider_name": "Sample Dr. Morgan Vale",
                    "decision_available": False,
                }
                return 200, self.application_state
            if path.endswith("/reject"):
                self.application_state = {**self.application_state, "status": "REJECTED", "review_status": "REJECTED", "reviewed_at": STAMP, "reviewed_by_name": "Sample Admin"}
                return 200, self.application_state

        if path == "/api/v1/admin/provider-profile-updates" and method == "GET":
            return 200, paged([self.profile_update_state], query)
        if path in ("/api/v1/admin/provider-profile-updates/sample-profile-update", "/api/v1/admin/provider-applications/updates/sample-profile-update") and method == "GET":
            return 200, self.profile_update_state
        if path.startswith("/api/v1/admin/provider-profile-updates/sample-profile-update/") and method == "POST":
            status = "APPROVED" if path.endswith("/approve") else "REJECTED"
            self.profile_update_state = {
                **self.profile_update_state,
                "review_status": status,
                "status": status,
                "reviewed_at": STAMP,
                "reviewed_by_name": "Sample Admin",
                "rejection_reason": "Sample decision preview only." if status == "REJECTED" else None,
            }
            return 200, self.profile_update_state

        if path == "/api/v1/admin/invitations" and method == "GET":
            return 200, paged(INVITATIONS, query)
        if path.startswith("/api/v1/admin/invitations/") and method == "GET":
            invitation_id = path.split("/")[-1]
            return 200, next((row for row in INVITATIONS if row["id"] == invitation_id), INVITATIONS[0])
        if path == "/api/v1/admin/invitations" and method == "POST":
            payload = body if isinstance(body, dict) else {}
            created = {
                "id": "sample-invitation-created",
                "recipient_email": payload.get("recipient_email", "sample.invitee@example.test"),
                "provider_type": payload.get("provider_type", "CLINIC"),
                "provider_name": payload.get("provider_name", "Sample New Clinic"),
                "status": "PENDING",
                "sent_at": STAMP,
                "expires_at": "2026-11-01T10:30:00Z",
                "accepted_at": None,
                "completed_at": None,
                "portal_access_created_at": None,
            }
            return 201, created
        if path.startswith("/api/v1/admin/invitations/") and method in ("POST", "PATCH", "DELETE"):
            return 200, {"message": "Sample invitation action preview only; no invitation email or real account was created."}

        if path == "/api/v1/admin/reviews" and method == "GET":
            return 200, paged([self.review_state], query)
        if path == "/api/v1/admin/reviews/sample-review" and method == "GET":
            return 200, self.review_state
        if path == "/api/v1/admin/reviews/sample-review/status" and method == "PATCH":
            status = body.get("status", "PENDING") if isinstance(body, dict) else "PENDING"
            self.review_state = {
                **self.review_state,
                "status": status,
                "comment_visible": status == "PUBLISHED",
                "updated_at": STAMP,
                "version": self.review_state["version"] + 1,
                "history": [
                    *self.review_state["history"],
                    {
                        "id": "sample-review-history-result",
                        "actor_id": "sample-admin",
                        "actor_name": "Sample Admin",
                        "actor_email": "sample.admin@example.test",
                        "actor_type": "admin",
                        "action": status.lower(),
                        "from_status": self.review_state["status"],
                        "to_status": status,
                        "version": self.review_state["version"] + 1,
                        "content_snapshot": {"comment": self.review_state["comment"], "sample": True},
                        "created_at": STAMP,
                    },
                ],
            }
            return 200, self.review_state

        if path == "/api/v1/admin/subscribers" and method == "GET":
            return 200, paged(SUBSCRIBERS, query)
        if path.startswith("/api/v1/admin/subscribers/") and method in ("PATCH", "DELETE"):
            return 200, {"message": "Sample subscriber fixture updated in browser only."}

        if path == "/api/v1/admin/contact-enquiries" and method == "GET":
            return 200, paged([self.contact_state], query)
        if path == "/api/v1/admin/contact-enquiries/sample-contact-enquiry" and method == "GET":
            return 200, self.contact_state
        if path == "/api/v1/admin/feedback" and method == "GET":
            return 200, paged([self.feedback_state], query)
        if path == "/api/v1/admin/feedback/sample-feedback" and method == "GET":
            return 200, self.feedback_state
        if path.startswith("/api/v1/admin/feedback/sample-feedback/") and method in ("PATCH", "POST"):
            self.feedback_state = {
                **self.feedback_state,
                "status": "Resolved",
                "updated_at": STAMP,
                "version": 2,
                "internal_note": "Sample resolution note in browser fixture.",
                "history": [{
                    "id": "sample-feedback-history",
                    "actor_id": "sample-admin",
                    "actor_name": "Sample Admin",
                    "actor_email": "sample.admin@example.test",
                    "actor_type": "admin",
                    "action": "resolved",
                    "from_status": "Pending",
                    "to_status": "Resolved",
                    "version": 2,
                    "content_snapshot": {"sample": True},
                    "created_at": STAMP,
                }],
            }
            return 200, self.feedback_state

        if path == "/api/v1/admin/activity-logs" and method == "GET":
            return 200, paged(ACTIVITY_LOGS, query)
        if path == "/api/v1/admin/email-logs" and method == "GET":
            return 200, paged(EMAIL_LOGS, query)
        if path == "/api/v1/admin/analytics" and method == "GET":
            return 200, {"data": [], "meta": {"page": 1, "page_size": 25, "total": 0, "total_pages": 1}}

        # Generic success fixtures for remaining known API write families. They
        # never forward to the application backend or an external service.
        known_write_prefixes = (
            "/api/v1/admin/providers/",
            "/api/v1/admin/doctors/",
            "/api/v1/admin/specializations/",
            "/api/v1/admin/languages/",
        )
        if method not in ("GET", "HEAD", "OPTIONS") and path.startswith(known_write_prefixes):
            return 200, {"message": "Sample browser-only fixture response; no live data changed."}

        self.unknown.append(f"{method} {path}")
        return 599, {
            "detail": {
                "code": "manual_fixture_missing",
                "message": f"Manual capture fixture does not define this endpoint: {method} {path}.",
            }
        }


@dataclass
class Target:
    id: str
    websocket_url: str


class CDP:
    def __init__(self, websocket_url: str, fixtures: FixtureAPI) -> None:
        self.websocket_url = websocket_url
        self.fixtures = fixtures
        self.ws: Any = None
        self.next_id = 1
        self.pending: dict[int, asyncio.Future[Any]] = {}
        self.reader: asyncio.Task[Any] | None = None
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.responses_seen = 0

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.websocket_url, max_size=50 * 1024 * 1024)
        self.reader = asyncio.create_task(self._reader())
        await self.command("Page.enable")
        await self.command("Runtime.enable")
        await self.command("Log.enable")
        await self.command(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": self._sample_badge_script()},
        )
        await self.command(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": "*://*/api/v1/*", "requestStage": "Request"},
                    {"urlPattern": "*://*/uploads/providers/*", "requestStage": "Request"},
                ],
                "handleAuthRequests": True,
            },
        )

    def _sample_badge_script(self) -> str:
        return """
(() => {
  const addSampleBadge = () => {
    if (!document.body || document.getElementById('manual-sample-data-banner')) return false;
    const badge = document.createElement('div');
    badge.id = 'manual-sample-data-banner';
    badge.textContent = 'SAMPLE DATA — demonstration only';
    badge.setAttribute('role', 'note');
    badge.setAttribute('aria-label', 'SAMPLE DATA — demonstration only');
    badge.style.cssText = [
      'position:fixed', 'z-index:2147483647', 'top:10px', 'right:104px',
      'padding:8px 12px', 'border:2px solid #805400', 'border-radius:7px',
      'background:#fff0b3', 'color:#392300', 'font:700 13px/1.2 Arial,sans-serif',
      'letter-spacing:.2px', 'box-shadow:0 2px 8px rgba(25,20,10,.28)',
      'pointer-events:none', 'white-space:nowrap'
    ].join(';');
    document.body.appendChild(badge);
    return true;
  };
  if (addSampleBadge()) return;
  if (!document.documentElement) {
    document.addEventListener('DOMContentLoaded', addSampleBadge, { once:true });
    return;
  }
  const observer = new MutationObserver(() => {
    if (addSampleBadge()) observer.disconnect();
  });
  observer.observe(document.documentElement, { childList:true, subtree:true });
  document.addEventListener('DOMContentLoaded', () => addSampleBadge(), { once:true });
})();
"""

    async def command(self, method: str, params: dict[str, Any] | None = None) -> Any:
        command_id = self.next_id
        self.next_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[command_id] = future
        await self.ws.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
        response = await asyncio.wait_for(future, timeout=30)
        if "error" in response:
            raise RuntimeError(f"CDP {method} failed: {response['error']}")
        return response.get("result", {})

    async def _reader(self) -> None:
        async for raw in self.ws:
            message = json.loads(raw)
            if "id" in message:
                future = self.pending.pop(message["id"], None)
                if future and not future.done():
                    future.set_result(message)
                continue
            method = message.get("method", "")
            params = message.get("params", {})
            if method == "Fetch.requestPaused":
                asyncio.create_task(self._handle_request(params))
            elif method == "Runtime.exceptionThrown":
                details = params.get("exceptionDetails", {})
                exception = details.get("exception", {})
                description = exception.get("description") or details.get("text") or "JavaScript exception"
                self.page_errors.append(
                    str(description)
                )
            elif method == "Log.entryAdded":
                entry = params.get("entry", {})
                if entry.get("level") == "error":
                    self.console_errors.append(str(entry.get("text", "")))

    async def _handle_request(self, params: dict[str, Any]) -> None:
        request_id = params["requestId"]
        request = params.get("request", {})
        url = request.get("url", "")
        parsed = urllib.parse.urlparse(url)
        try:
            if parsed.path.startswith("/api/v1/"):
                body = None
                raw_body = request.get("postData")
                if raw_body:
                    try:
                        body = json.loads(raw_body)
                    except (json.JSONDecodeError, TypeError):
                        body = raw_body
                status, response = self.fixtures.route(
                    url,
                    request.get("method", "GET").upper(),
                    body,
                )
                await self._fulfill(
                    request_id,
                    status,
                    json.dumps(response, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return

            if parsed.path.startswith("/uploads/providers/"):
                filename = Path(parsed.path).name
                asset_path = ROOT / "frontend" / "public" / filename
                if not asset_path.is_file():
                    asset_path = ROOT / "frontend" / "public" / "horse-panel.jpg"
                content_type = "image/jpeg" if asset_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                await self._fulfill(request_id, 200, asset_path.read_bytes(), content_type)
                return

            # Any non-API request matched by the interception pattern is also
            # denied explicitly instead of being continued to a server.
            self.fixtures.unknown.append(f"NON_API {request.get('method', 'GET')} {parsed.path}")
            await self._fulfill(
                request_id,
                599,
                b"Manual capture fixture missing",
                "text/plain; charset=utf-8",
            )
        except Exception as exc:
            self.fixtures.failures.append(f"{request.get('method')} {url}: {exc}")
            await self._fulfill(
                request_id,
                599,
                json.dumps({"detail": {"code": "fixture_error", "message": str(exc)}}).encode(),
                "application/json; charset=utf-8",
            )

    async def _fulfill(
        self,
        request_id: str,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        self.responses_seen += 1
        await self.command(
            "Fetch.fulfillRequest",
            {
                "requestId": request_id,
                "responseCode": status,
                "responseHeaders": [
                    {"name": "Content-Type", "value": content_type},
                    {"name": "Cache-Control", "value": "no-store"},
                ],
                "body": base64.b64encode(body).decode("ascii"),
            },
        )

    async def evaluate(self, expression: str, await_promise: bool = True) -> Any:
        result = await self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
                "userGesture": True,
            },
        )
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text", "JavaScript evaluation failed"))
        return result.get("result", {}).get("value")

    async def wait_for(self, expression: str, timeout: float = 18) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.evaluate(expression, await_promise=False):
                return
            await asyncio.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for page condition: {expression}")

    async def navigate(self, path: str) -> None:
        await self.command("Page.navigate", {"url": BASE_URL + path})
        await self.wait_for("document.readyState === 'complete'", timeout=20)
        await asyncio.sleep(1.9)
        await self.evaluate(self._sample_badge_script())
        await self.wait_for("document.querySelector('#manual-sample-data-banner') !== null", timeout=5)

    async def screenshot(self, output: Path) -> None:
        result = await self.command(
            "Page.captureScreenshot",
            {
                "format": "png",
                "captureBeyondViewport": False,
                "fromSurface": True,
            },
        )
        output.write_bytes(base64.b64decode(result["data"]))

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()


BASE_URL = ""


def find_chrome() -> str:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    raise RuntimeError("Chromium was not found in PATH.")


async def create_target() -> tuple[Target, subprocess.Popen[bytes], Path]:
    import urllib.request

    chrome = find_chrome()
    profile = Path("/tmp") / f"manual-admin-chrome-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True)
    process = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-component-update",
            "--disable-features=OptimizationHints,MediaRouter",
            "--ignore-certificate-errors",
            "--no-sandbox",
            "--headless=new",
            f"--window-size={WIDTH},{HEIGHT}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    endpoint = f"http://127.0.0.1:{CDP_PORT}/json"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=1) as response:
                targets = json.loads(response.read())
            page_targets = [item for item in targets if item.get("type") == "page"]
            if page_targets:
                target = page_targets[0]
                return Target(target["id"], target["webSocketDebuggerUrl"]), process, profile
        except Exception:
            time.sleep(0.2)
    process.terminate()
    raise RuntimeError(f"Isolated Chromium did not expose a page on CDP port {CDP_PORT}.")


async def click_text(cdp: CDP, text: str, exact: bool = True) -> bool:
    expression = (
        "(async () => {"
        " const wanted = " + json.dumps(text) + ";"
        " const candidates = [...document.querySelectorAll('button,a,[role=button],summary')];"
        " const matches = candidates.filter(el => {"
        "   const value = (el.innerText || el.getAttribute('aria-label') || '').trim();"
        + ("   return value === wanted;" if exact else "   return value.toLowerCase().includes(wanted.toLowerCase());")
        + " });"
        " const target = matches[matches.length - 1];"
        " if (!target) return false;"
        " const rect = target.getBoundingClientRect();"
        " if (rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth)"
        "   target.scrollIntoView({block:'center', behavior:'instant'});"
        " target.click(); return true;"
        "})()"
    )
    return bool(await cdp.evaluate(expression))


async def click_aria(cdp: CDP, label: str) -> bool:
    return bool(await cdp.evaluate(
        """(() => {
          const wanted = %s;
          const target = [...document.querySelectorAll('button,a,[role=button]')]
            .find(el => el.getAttribute('aria-label') === wanted);
          if (!target) return false;
          target.scrollIntoView({block:'center', behavior:'instant'});
          target.click();
          return true;
        })()""" % json.dumps(label)
    ))


async def set_field(cdp: CDP, label: str, value: str) -> bool:
    expression = """(() => {
      const wanted = %s;
      const labels = [...document.querySelectorAll('label')];
      const label = labels.find(item => item.innerText.trim().replace(/\\s+/g, ' ') === wanted);
      let field = label?.querySelector('input,textarea,select');
      if (!field && label?.htmlFor) field = document.getElementById(label.htmlFor);
      if (!field) {
        const el = [...document.querySelectorAll('input,textarea,select')]
          .find(item => item.getAttribute('aria-label') === wanted);
        field = el;
      }
      if (!field) return false;
      const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype :
        field instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
      descriptor.set.call(field, %s);
      field.dispatchEvent(new Event('input', {bubbles:true}));
      field.dispatchEvent(new Event('change', {bubbles:true}));
      return true;
    })()""" % (json.dumps(label), json.dumps(value))
    return bool(await cdp.evaluate(expression))


async def set_select(cdp: CDP, label: str, option_text: str) -> bool:
    return await cdp.evaluate(
        """(() => {
          const wanted = %s, optionText = %s;
          const label = [...document.querySelectorAll('label')].find(x => x.innerText.trim() === wanted);
          let select = label?.querySelector('select');
          if (!select && label?.htmlFor) select = document.getElementById(label.htmlFor);
          if (!select) return false;
          const option = [...select.options].find(x => x.text.trim() === optionText);
          if (!option) return false;
          select.value = option.value;
          select.dispatchEvent(new Event('input', {bubbles:true}));
          select.dispatchEvent(new Event('change', {bubbles:true}));
          return true;
        })()""" % (json.dumps(label), json.dumps(option_text))
    )


async def scroll_to_text(cdp: CDP, text: str, selector: str | None = None) -> None:
    await cdp.evaluate(
        """(() => {
          const needle = %s;
          const selector = %s;
          const items = [...document.querySelectorAll(selector || 'h1,h2,h3,h4,[role=heading],button,[role=button]')];
          const element = items.find(x => (x.innerText || '').trim().includes(needle));
          if (element) {
            element.scrollIntoView({block:'start', behavior:'instant'});
            window.scrollBy(0, -82);
          }
        })()""" % (json.dumps(text), json.dumps(selector))
    )


async def capture(
    cdp: CDP,
    filename: str,
    topic: str,
    title: str,
    path: str,
    state: str,
    source: str,
    wait_for: str | None = None,
    scroll_text: str | None = None,
    selector: str | None = None,
) -> dict[str, str]:
    if path:
        await cdp.navigate(path)
    if wait_for:
        await cdp.wait_for(wait_for)
    if scroll_text:
        await scroll_to_text(cdp, scroll_text, selector)
        await asyncio.sleep(0.2)
    await cdp.wait_for("document.querySelector('#manual-sample-data-banner') !== null", timeout=4)
    body_text = (await cdp.evaluate("document.body.innerText || ''")) or ""
    if "SAMPLE DATA — demonstration only" not in body_text:
        raise RuntimeError(f"Missing visible sample-data notice while capturing {filename}")
    output = ASSET_DIR / filename
    png_output = output.with_suffix(".png")
    await cdp.screenshot(png_output)
    if shutil.which("cwebp"):
        subprocess.run(
            ["cwebp", "-quiet", "-q", "84", "-m", "6", str(png_output), "-o", str(output)],
            check=True,
        )
        png_output.unlink(missing_ok=True)
    else:
        output.write_bytes(png_output.read_bytes())
        png_output.unlink(missing_ok=True)
    if len(body_text.strip()) < 40:
        raise RuntimeError(f"Unexpectedly empty page while capturing {filename}")
    print(f"Captured {output.relative_to(ROOT)} ({len(body_text)} visible-text chars)")
    return {
        "topic": topic,
        "title": title,
        "file": filename,
        "route": path,
        "state": state,
        "source": source,
    }


async def wait_for_visible(cdp: CDP, text: str, timeout: float = 15) -> None:
    await cdp.wait_for(
        "document.body && document.body.innerText.includes(" + json.dumps(text) + ")",
        timeout=timeout,
    )


async def create_email_log_captures(cdp: CDP) -> list[dict[str, str]]:
    return [
        await capture(
            cdp,
            "admin-email-logs.webp",
            "admin-email-logs",
            "Email delivery logs",
            "/admin/email-logs",
            "Read-only email log shows synthetic accepted and failed delivery rows with date filters.",
            "Shipped EmailLogsPage; sample delivery rows are browser-only fixtures.",
            wait_for=(
                "document.body.innerText.includes('sample.owner@example.test')"
                " && document.body.innerText.includes('Accepted by SMTP')"
                " && document.body.innerText.includes('Failed')"
            ),
        ),
        await capture(
            cdp,
            "admin-email-logs-date-range.webp",
            "admin-email-logs",
            "Filter email logs by date range",
            "/admin/email-logs?filter_mode=range&date_from=2026-10-01&date_to=2026-10-01",
            "Read-only log view has a populated custom date range and retains synthetic accepted and failed rows.",
            "Shipped EmailLogsPage custom-range filters; results are browser-only sample fixtures.",
            wait_for=(
                "document.body.innerText.includes('Showing 2026-10-01 through 2026-10-01')"
                " && document.body.innerText.includes('sample.owner@example.test')"
                " && document.body.innerText.includes('Failed')"
            ),
        ),
    ]


async def create_captures(cdp: CDP) -> list[dict[str, str]]:
    captures: list[dict[str, str]] = []

    async def add(filename: str, topic: str, title: str, *details: str, **kwargs: Any) -> dict[str, str]:
        if len(details) == 3:
            path, state, source = details
        elif len(details) == 4 and details[1].startswith("/"):
            _, path, state, source = details
        elif len(details) == 4:
            path = details[0]
            state = f"{details[1]} {details[2]}".strip()
            source = details[3]
        else:
            raise ValueError(f"Capture metadata for {filename} must include route, state and source.")
        return await capture(cdp, filename, topic, title, path, state, source, **kwargs)

    # Dashboard and navigation.
    captures.append(await add(
        "admin-navigation.webp", "admin-navigation", "Admin navigation",
        "/admin/users", "Top-level admin navigation shows Dashboard and Registrations with the synthetic admin session.",
        "Shipped AdminTopNav; authenticated Sample Admin fixture, no dashboard capture.",
        wait_for="document.body.innerText.includes('Registered accounts')",
    ))
    await click_text(cdp, "Directory Management")
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-navigation-directory.webp", "admin-navigation", "Directory Management menu",
        "", "", "Actual Directory Management dropdown shows provider, application, catalog, invitation, and review destinations.",
        "Shipped AdminTopNav dropdown with no data beyond the visible Sample Admin identity.",
    ))
    await click_text(cdp, "Enquiries")
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-navigation-enquiries.webp", "admin-navigation", "Enquiries menu",
        "", "", "Actual Enquiries dropdown lists subscribers, contact enquiries, and platform feedback.",
        "Shipped AdminTopNav dropdown with synthetic navigation-only session.",
    ))
    await click_aria(cdp, "Open profile menu")
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-navigation-profile.webp", "admin-navigation", "Profile menu and workspace links",
        "", "Admin profile menu open with safe Sample Admin identity.",
        "Actual admin navigation menu opened in the running React app.",
        "Shipped AdminLayout menu; the browser-only admin session is supplied by this script.",
        wait_for="document.body.innerText.includes('Activity Logs')",
    ))

    # Registration review, with details modal.
    await cdp.navigate("/admin/users")
    await wait_for_visible(cdp, "Sample Taylor")
    captures.append(await add(
        "admin-registrations.webp", "admin-registrations", "Registered accounts",
        "/admin/users", "List shows two sample member registrations with different verification states.",
        "Shipped UsersPage; all user data is synthetic and supplied through intercepted requests.",
    ))
    await click_aria(cdp, "Actions for Sample Taylor Owner")
    await click_text(cdp, "View details", exact=False)
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-registrations-details.webp", "admin-registrations", "Registration details",
        "", "", "Sample member detail dialog displays verification and registration information.",
        "Shipped UsersPage detail dialog, opened for Sample Taylor Owner.",
        wait_for="document.body.innerText.includes('Email verification')",
    ))

    # Provider list and filters.
    captures.append(await add(
        "admin-provider-directory.webp", "provider-directory", "Provider directory",
        "/admin/providers", "Directory shows sample clinic, doctor, and hospital with independent status/publication states.",
        "Shipped ProvidersPage and existing filter controls; three synthetic providers.",
        wait_for="document.body.innerText.includes('Sample Meadow Equine Clinic')",
    ))
    filter_open = await click_text(cdp, "Filters", exact=False)
    if filter_open:
        await asyncio.sleep(0.2)
        captures.append(await add(
            "provider-directory-filters.webp", "provider-directory", "Provider directory filters",
            "", "", "Provider-type, services, status, and publication filters expanded.",
            "Shipped ProvidersPage filter drawer with sample directory rows.",
        ))
    await click_aria(cdp, "Actions for Sample Meadow Equine Clinic")
    await asyncio.sleep(0.2)
    captures.append(await add(
        "provider-directory-actions.webp", "provider-directory", "Provider lifecycle actions",
        "", "", "Actual provider row action menu shows state-dependent management controls for a Published sample clinic.",
        "Shipped ProvidersPage row ActionMenu with synthetic provider state.",
    ))
    captures.append(await add(
        "admin-provider-lifecycle.webp", "provider-lifecycle-publication", "Status and publication controls",
        "", "", "Provider list keeps Active/Inactive status distinct from Published/Unpublished directory visibility.",
        "Shipped ProvidersPage with independent status and publication badges; row action menu is fixture-only.",
    ))

    # Create wizard controls, populated but never submitted.
    captures.append(await add(
        "provider-create.webp", "provider-create", "Create provider wizard",
        "/admin/providers/new", "First step of the actual create-provider wizard, with Sample data entered; no provider was submitted.",
        "Shipped ProviderForm; the API catalogs are intercepted synthetic values.",
        wait_for="document.body.innerText.includes('Provider / practice name')",
    ))
    await set_select(cdp, "Provider type", "Doctor / Vet")
    await asyncio.sleep(0.2)
    await set_field(cdp, "Provider / practice name", "Sample Dr. New Field")
    await set_field(cdp, "First name", "Sample New")
    await set_field(cdp, "Last name", "Field")
    await set_field(cdp, "Professional title", "Sample Equine Veterinarian")
    await set_field(cdp, "Years of experience", "8")
    await set_field(cdp, "Biography", "Sample biography for the create-provider wizard.")
    captures.append(await add(
        "admin-provider-create-populated.webp", "provider-create", "Create a doctor profile",
        "", "", "Doctor-specific form shows Sample identity, professional title, experience and biography; no provider is saved.",
        "Shipped ProviderForm create flow using synthetic inputs and fixture catalogs.",
    ))
    await click_text(cdp, "Next", exact=False)
    await asyncio.sleep(0.4)
    await click_text(cdp, "Next", exact=False)
    await asyncio.sleep(0.3)
    await click_text(cdp, "Next", exact=False)
    await asyncio.sleep(0.3)
    await set_field(cdp, "Email", "sample.new-doctor@example.test")
    await set_field(cdp, "Location name", "Sample New Office")
    await set_field(cdp, "Address line 1", "400 Sample Lane")
    await set_field(cdp, "City", "Sample Meadow")
    await set_field(cdp, "Country", "Sample Country")
    await set_field(cdp, "Pincode / postal code", "00003")
    await click_text(cdp, "Next", exact=False)
    await asyncio.sleep(0.4)
    captures.append(await add(
        "provider-create-review.webp", "provider-create", "Review new provider",
        "", "", "Review & create summary contains only synthetic Sample values; Create provider is not clicked.",
        "Shipped ProviderForm review step with unsaved browser-only sample input.",
        wait_for="document.body.innerText.includes('Review & create')",
    ))

    # Existing provider edit wizard, with the loaded saved values visible.
    captures.append(await add(
        "provider-edit.webp", "provider-edit", "Edit provider wizard",
        "/admin/providers/sample-doctor/edit", "Actual edit wizard is pre-populated from the Sample Dr. Avery Field record; no fields are saved.",
        "Shipped ProviderEditPage and ProviderForm with browser-intercepted profile data.",
        wait_for="document.body.innerText.includes('Provider / practice name')",
    ))

    # Provider detail: portal access state, profile data, contacts, visits,
    # photos, and qualifications. Nothing is changed except form expansion.
    captures.append(await add(
        "provider-record-details.webp", "provider-record-details", "Provider profile and detail sections",
        "/admin/providers/sample-doctor", "Top of Sample Dr. Avery Field profile shows overview and reset-access controls. No email is sent.",
        "Shipped ProviderDetailPage; sample profile and access status returned by the isolated fixture.",
        wait_for="document.body.innerText.includes('Provider portal access')",
    ))
    captures.append(await add(
        "provider-portal-access-recovery.webp", "provider-portal-access-recovery", "Provider portal access",
        "", "", "Doctor access panel shows Sample recipient, current reset status and the reset action. Nothing is sent.",
        "Shipped ProviderDetailPage portal-access panel with a fixture-only active account state.",
        scroll_text="Provider portal access", selector="h2",
    ))
    await scroll_to_text(cdp, "Qualifications", "h2")
    await asyncio.sleep(0.25)
    captures.append(await add(
        "provider-profile-collections.webp", "provider-profile-collections", "Doctor qualifications",
        "", "", "Sample doctor qualifications and the add/edit/remove controls.",
        "Shipped DoctorProfessionalSections with sample doctor qualification records.",
    ))
    await click_text(cdp, "＋ Add qualification", exact=False)
    await asyncio.sleep(0.25)
    await set_field(cdp, "Title", "Sample Advanced Equine Certificate")
    await set_field(cdp, "Institution", "Sample Learning Centre")
    await set_field(cdp, "Year obtained", "2024")
    captures.append(await add(
        "provider-profile-qualification-form.webp", "provider-profile-collections", "Qualification form",
        "", "", "Actual qualification form filled with unsaved Sample values; Add qualification is not submitted.",
        "Shipped DoctorProfessionalSections inline form; form data is not sent.",
    ))
    await scroll_to_text(cdp, "Locations", "h2")
    await asyncio.sleep(0.15)
    await click_text(cdp, "＋ Add location", exact=False)
    await asyncio.sleep(0.2)
    await set_field(cdp, "Location name", "Sample Annex")
    await set_field(cdp, "Address line 1", "600 Sample Lane")
    captures.append(await add(
        "provider-profile-locations.webp", "provider-profile-collections", "Manage a provider location",
        "", "", "Location editor is populated with sample address values; the location is not saved.",
        "Shipped ProviderDetailPage location form with browser-only fixture input.",
    ))
    await click_text(cdp, "Cancel", exact=False)
    await scroll_to_text(cdp, "Doctor trips", "h2")
    await asyncio.sleep(0.2)
    captures.append(await add(
        "admin-doctor-visits.webp", "provider-doctor-visits", "Doctor visits",
        "", "", "Visiting availability with previous and upcoming synthetic visit periods.",
        "Shipped ProviderDetailPage Doctor trips section; dates and locations are fixtures.",
    ))
    await click_text(cdp, "Add future return", exact=False)
    await asyncio.sleep(0.2)
    await set_field(cdp, "Location name", "Sample Winter Visit")
    await set_field(cdp, "Address line 1", "500 Sample Trail")
    await set_field(cdp, "City", "Sample Ridge")
    await set_field(cdp, "Country", "Sample Country")
    await set_field(cdp, "Postal code", "00004")
    await set_field(cdp, "Start date", FUTURE_START)
    await set_field(cdp, "End date", FUTURE_END)
    captures.append(await add(
        "provider-doctor-visits-add-form.webp", "provider-doctor-visits", "Schedule a future visit",
        "", "", "Visit-period form uses sample location/date values; Add return is not submitted.",
        "Shipped ProviderDetailPage visit editor with synthetic values only.",
    ))
    captures.append(await add(
        "admin-provider-visiting-calendar.webp", "provider-visiting-calendar", "Admin visiting-provider calendar",
        "/admin/visiting-providers", "Month calendar with a sample visit spanning the selected day and a provider-linked agenda card.",
        "Shipped AdminVisitingProviderCalendarPage and VisitingProviderCalendar with fixture month data.",
        wait_for="document.body.innerText.includes('Sample Dr. Avery Field')",
    ))
    await cdp.navigate("/admin/providers/sample-doctor")
    await scroll_to_text(cdp, "Photos", "h2")
    await asyncio.sleep(0.2)
    captures.append(await add(
        "provider-photo-management.webp", "provider-photo-management", "Provider photos",
        "", "", "Gallery displays safe local horse/stable sample imagery, alt text, profile-photo state, and management controls.",
        "Shipped ProviderDetailPage Photos section; images are the two existing, inspected local assets, with synthetic metadata.",
    ))
    await click_text(cdp, "＋ Add photos", exact=False)
    await asyncio.sleep(0.2)
    captures.append(await add(
        "provider-photo-upload.webp", "provider-photo-management", "Stage provider photos",
        "", "", "Actual upload panel documents supported photo formats, size limit, metadata fields and deferred upload.",
        "Shipped ProviderDetailPage upload panel opened; no file is uploaded.",
    ))
    await cdp.navigate("/admin/providers/sample-clinic")
    await wait_for_visible(cdp, "Provider portal access")
    await click_text(cdp, "Send password setup email", exact=False)
    await asyncio.sleep(0.5)
    captures.append(await add(
        "provider-portal-access-setup-preview.webp", "provider-portal-access-recovery", "Setup request result preview",
        "", "", "Fixture explicitly reports a setup-request preview; no email was sent.",
        "Shipped ProviderDetailPage result state after an intercepted fixture-only action.",
        wait_for="document.body.innerText.includes('No email was sent')",
    ))

    # Provider application details and a simulated, browser-only review result.
    await cdp.navigate("/admin/provider-applications")
    await wait_for_visible(cdp, "Sample Dr. Morgan Vale")
    captures.append(await add(
        "admin-provider-applications.webp", "provider-applications", "Provider applications",
        "", "/admin/provider-applications", "Pending sample application appears in the actual review queue.",
        "Shipped ProviderApplicationsPage with one synthetic pending application.",
    ))
    await click_aria(cdp, "Actions for Sample Dr. Morgan Vale")
    await click_text(cdp, "View application", exact=False)
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-application-details.webp", "provider-applications", "Inspect an application",
        "", "", "Application detail shows sample professional, contact, service, consent and verification fields.",
        "Shipped ProviderApplicationsPage application detail modal.",
    ))
    await click_text(cdp, "Approve & stage listing", exact=False)
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-application-approval-confirm.webp", "provider-applications", "Approval confirmation",
        "", "", "Confirmation explains staged-draft result; all action requests are fixture-only.",
        "Shipped ProviderApplicationsPage decision confirmation dialog.",
    ))
    await click_text(cdp, "Approve application", exact=False)
    await asyncio.sleep(0.6)
    captures.append(await add(
        "admin-application-staged-result.webp", "provider-applications", "Sample approval result",
        "", "", "The UI shows the sample application as reviewed and identifies the staged listing as a draft; the fixture has no live record or email.",
        "Shipped ProviderApplicationsPage result handling; POST fulfilled by the isolated browser fixture.",
        wait_for="document.body.innerText.includes('This application has already been reviewed.')",
    ))

    # Profile update comparison, with a separate sample-only decision result.
    await cdp.navigate("/admin/provider-applications?tab=updates")
    await wait_for_visible(cdp, "Sample Dr. Avery Field")
    if not await cdp.evaluate("document.body.innerText.includes('Photo comparison')"):
        await click_text(cdp, "Updates", exact=False)
        await asyncio.sleep(0.6)
    captures.append(await add(
        "admin-provider-updates.webp", "provider-profile-updates", "Provider updates queue",
        "", "/admin/provider-applications?tab=updates", "One pending sample profile update is available for comparison.",
        "Shipped ProviderApplicationsPage Updates view with a synthetic pending change.",
    ))
    if not await click_aria(cdp, "Actions for Sample Dr. Avery Field update"):
        raise RuntimeError("The provider update Actions menu was not found.")
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-provider-update-actions.webp", "provider-profile-updates", "Provider update actions",
        "", "", "The actual profile-update row menu exposes Compare profiles.",
        "Shipped ProviderApplicationsPage row ActionMenu using a synthetic pending update.",
    ))
    if not await click_text(cdp, "Compare profiles", exact=False):
        raise RuntimeError("The Compare profiles action was not found in the provider update menu.")
    await asyncio.sleep(0.45)
    captures.append(await add(
        "admin-provider-update-comparison.webp", "provider-profile-updates", "Compare profile and photos",
        "", "", "Actual comparison shows current/proposed sample values and an added photo with safe fixture images.",
        "Shipped ProviderApplicationsPage comparison modal; both profile and photo data are synthetic.",
        wait_for="document.body.innerText.includes('Review provider profile update') && document.body.innerText.includes('Proposed photos')",
    ))
    await click_text(cdp, "Approve update", exact=False)
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-provider-update-confirm.webp", "provider-profile-updates", "Confirm update decision",
        "", "", "Sample update decision confirmation remains entirely in the fixture browser.",
        "Shipped ProviderApplicationsPage profile-update confirmation dialog.",
    ))
    await click_text(cdp, "Approve update", exact=False)
    await asyncio.sleep(0.5)
    captures.append(await add(
        "admin-provider-update-result.webp", "provider-profile-updates", "Sample update result",
        "", "", "Fixture-only approved state appears in the real page; no live profile is changed.",
        "Shipped ProviderApplicationsPage update-result state after intercepted browser-only decision.",
        wait_for="document.body.innerText.includes('Approved')",
    ))

    # Invitations list presents all workflow states. Create form is populated
    # with sample values but never submitted; no invitation/setup token appears.
    await cdp.navigate("/admin/invitations")
    await wait_for_visible(cdp, "sample.pending@example.test")
    captures.append(await add(
        "admin-invitations-statuses.webp", "provider-invitations", "Invitation statuses",
        "", "/admin/invitations", "Sample invitations show Pending, Accepted, Expired, Cancelled, and Completed states.",
        "Shipped InvitationsPage; entries, emails and dates are sample fixtures; no raw link is included.",
    ))
    await click_text(cdp, "New invitation", exact=False)
    await asyncio.sleep(0.25)
    await set_select(cdp, "Provider type", "Doctor")
    await set_field(cdp, "First name", "Sample Jamie")
    await set_field(cdp, "Last name", "Field")
    await set_field(cdp, "Recipient email", "sample.invitee@example.test")
    captures.append(await add(
        "admin-invitation-create.webp", "provider-invitations", "Create invitation",
        "", "", "Doctor invitation form is populated with Sample values; Send invitation is not clicked.",
        "Shipped CreateInvitationDialog; no invitation is generated or email sent.",
    ))

    # Catalog CRUD and CSV preview. The fixture file is synthetic and never
    # imported; the dialog remains on the live UI's preview step.
    await cdp.navigate("/admin/specializations")
    await wait_for_visible(cdp, "Sample Equine Medicine")
    captures.append(await add(
        "admin-specializations.webp", "specializations-catalog", "Specializations catalog",
        "", "/admin/specializations", "Specializations table and catalog actions use safe Sample entries.",
        "Shipped SpecializationsPage and browser-intercepted catalog response.",
    ))
    await click_text(cdp, "Import", exact=False)
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-specialization-csv-upload.webp", "specializations-catalog", "CSV upload",
        "", "", "Actual CSV dialog shows template link, format, and size constraints before file selection.",
        "Shipped CsvImportDialog; no file or template request leaves the browser.",
    ))
    await cdp.evaluate("""(() => {
      const input = document.querySelector('input[type=file][accept*=".csv"]');
      if (!input) return false;
      const file = new File([
        'Name,Description,Status\\nSample Equine Sports Medicine,Sample valid CSV row,ACTIVE\\nSample Equine Medicine,Sample duplicate CSV row,ACTIVE\\n,Sample invalid CSV row,ACTIVE'
      ], 'sample-specializations.csv', {type:'text/csv'});
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event('change', {bubbles:true}));
      return true;
    })()""")
    await asyncio.sleep(0.75)
    captures.append(await add(
        "admin-specialization-csv-preview.webp", "specializations-catalog", "CSV preview",
        "", "", "CSV preview shows one valid, one duplicate and one invalid Sample row; Import is not clicked.",
        "Shipped CsvImportDialog preview; its preview endpoint is intercepted and no data is saved.",
        wait_for="document.body.innerText.includes('Duplicates:')",
    ))

    # Language catalog is a separate shipped admin workspace.
    await cdp.navigate("/admin/languages")
    await wait_for_visible(cdp, "Sample English")
    captures.append(await add(
        "admin-languages.webp", "languages-catalog", "Languages catalog",
        "", "/admin/languages", "Searchable language catalog shows fixture language names and codes.",
        "Shipped LanguagesPage with synthetic language records.",
    ))
    await click_text(cdp, "Add language", exact=False)
    await asyncio.sleep(0.2)
    captures.append(await add(
        "admin-language-form.webp", "languages-catalog", "Add a language",
        "", "", "Actual language dialog displays name and code fields without saving a catalog record.",
        "Shipped LanguageForm in LanguagesPage; no mutation is submitted.",
    ))

    # Moderation list/detail and fixture-only publish outcome.
    await cdp.navigate("/admin/reviews")
    await wait_for_visible(cdp, "Sample Meadow Equine Clinic")
    captures.append(await add(
        "admin-reviews-moderation.webp", "provider-reviews-moderation", "Review moderation queue",
        "", "/admin/reviews", "Sample pending provider review appears in the queue.",
        "Shipped ReviewsPage with synthetic member, comment and provider details.",
    ))
    await click_text(cdp, "View", exact=False)
    await asyncio.sleep(0.3)
    captures.append(await add(
        "admin-review-details.webp", "provider-reviews-moderation", "Review details and history",
        "", "", "Sample comment, moderation history and actions appear in the real details view.",
        "Shipped ReviewsPage detail interaction and fixture response.",
    ))
    await click_text(cdp, "Approve & publish", exact=False)
    await asyncio.sleep(0.5)
    captures.append(await add(
        "admin-review-publish-result.webp", "provider-reviews-moderation", "Sample moderation result",
        "", "", "Published state and synthetic moderation-history entry appear after an intercepted request.",
        "Shipped ReviewsPage; POST response updates only browser fixture state.",
        wait_for="document.body.innerText.includes('Published')",
    ))

    # Subscriber, enquiry and private feedback inboxes.
    captures.append(await add(
        "admin-subscribers.webp", "admin-subscribers", "Subscribers",
        "/admin/subscribers", "Sample subscriber records show synthetic emails, registration types and dates.",
        "Shipped SubscribersPage with synthetic .example.test addresses.",
        wait_for="document.body.innerText.includes('sample.subscriber@example.test')",
    ))
    captures.append(await add(
        "admin-contact-enquiries.webp", "admin-contact-enquiries", "Contact enquiries",
        "/admin/contact-enquiries", "Sample enquiry is visible in the inbox.",
        "Shipped ContactEnquiriesPage; the contact message is explicitly synthetic.",
        wait_for="document.body.innerText.includes('Sample Riley Contact')",
    ))
    await click_text(cdp, "View", exact=False)
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-contact-enquiry-detail.webp", "admin-contact-enquiries", "Contact enquiry detail",
        "", "", "Read-only sample message and sender details; no reply or outbound action is available.",
        "Shipped ContactEnquiriesPage detail route with synthetic text and an intercepted detail read.",
    ))
    captures.append(await add(
        "admin-private-feedback.webp", "admin-platform-feedback", "Platform feedback inbox",
        "/admin/feedback", "One sample feedback entry with a private message.",
        "Shipped PlatformFeedbackPage with synthetic .example.test identity and text.",
        wait_for="document.body.innerText.includes('Sample Quinn Feedback')",
    ))
    await click_text(cdp, "View", exact=False)
    await asyncio.sleep(0.25)
    captures.append(await add(
        "admin-private-feedback-detail.webp", "admin-platform-feedback", "Private feedback detail",
        "", "", "Synthetic feedback message, resolution state and notes; no public display or email.",
        "Shipped PlatformFeedbackDetailPage using only intercepted sample data.",
    ))

    # Logs, settings and navigation controls.
    captures.append(await add(
        "admin-activity-logs.webp", "admin-activity-logs", "Activity log",
        "/admin/activity-logs", "Synthetic Sample Admin events and reserved documentation IP addresses.",
        "Shipped ActivityLogsPage; all records are synthetic (RFC 5737 documentation-only IP range).",
        wait_for="document.body.innerText.includes('Sample Admin')",
    ))
    await click_text(cdp, "1 changed field", exact=False)
    captures.append(await add(
        "admin-activity-log-details.webp", "admin-activity-logs", "Activity change details",
        "", "", "Expanded activity entry shows the sample before/after review-status change.",
        "Shipped ActivityLogsPage change disclosure with fixture-supplied before/after content.",
    ))
    captures.extend(await create_email_log_captures(cdp))
    captures.append(await add(
        "admin-settings.webp", "admin-settings", "Admin settings",
        "/admin/settings", "Actual settings fields show fixture timezone and formatting choices; nothing is saved.",
        "Shipped SettingsPage with a static synthetic settings response.",
        wait_for="document.body.innerText.includes('Timezone')",
    ))
    await click_aria(cdp, "Open profile menu")
    if not await click_text(cdp, "Logout", exact=False):
        raise RuntimeError("The profile menu Logout action was not found.")
    await cdp.wait_for("document.querySelector('[data-testid=\"admin-login-page\"]') !== null")
    await set_field(cdp, "Email address", "sample.admin@example.test")
    await set_field(cdp, "Password", "")
    if not await cdp.evaluate(
        """(() => {
          const password = document.querySelector('#admin-password');
          if (!password || password.value !== '') return false;
          password.placeholder = '';
          return true;
        })()"""
    ):
        raise RuntimeError("The login screenshot password field must remain empty.")
    captures.append(await add(
        "admin-sign-in-out.webp", "admin-sign-in-out", "Admin sign-in form",
        "", "", "Signed-out admin login form contains a Sample .example.test address and an empty password field; no credentials are submitted.",
        "Shipped LoginPage after intercepted logout; login remains idle and no password or auth request is sent.",
        wait_for="document.body.innerText.includes('Admin sign in')",
    ))
    return captures


def write_provenance(captures: list[dict[str, str]], api: FixtureAPI, target_id: str) -> None:
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in captures:
        grouped.setdefault(item["topic"], []).append(item)
    mapping = [
        "export type AdminManualScreenshot = { src: string; alt: string; caption: string };",
        "",
        "export const adminScreenshots: Record<string, AdminManualScreenshot[]> = {",
    ]
    for topic, items in grouped.items():
        mapping.append(f"  {json.dumps(topic, ensure_ascii=False)}: [")
        for item in items:
            source = "/manual/" + item["file"]
            alt = item["title"]
            caption = f"{item['title']}. {item['state']}"
            mapping.append(
                "    { "
                f"src: {json.dumps(source, ensure_ascii=False)}, "
                f"alt: {json.dumps(alt, ensure_ascii=False)}, "
                f"caption: {json.dumps(caption, ensure_ascii=False)} "
                "},"
            )
        mapping.append("  ],")
    mapping.append("};")
    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_PATH.write_text("\n".join(mapping) + "\n", encoding="utf-8")
    lines = [
        "# Admin manual screenshots",
        "",
        "## Provenance and safety",
        "",
        "These assets are screenshots of the shipped admin React application, not mockups. The reproducible capture script is `scripts/capture-manual-admin.py`. It launches a dedicated headless Chromium process with a unique user-data directory and connects to the `type: page` CDP target on port 9241. The signed-in display identity and every `/api/v1` response are synthetic fixtures fulfilled in the browser by CDP Fetch interception before the request can reach an application server.",
        "",
        "- Every captured screen has a visible `SAMPLE DATA — demonstration only` DOM overlay.",
        "- All synthetic person/provider names begin with `Sample`; all email addresses use the reserved `.example.test` domain.",
        "- Example messages, locations, profile data, application decisions and mutation outcomes are fictional and stay in this browser fixture.",
        "- Email, invitation and provider-access actions are intercepted. No login credentials, SMTP, invitation/setup links, external account, database record or backend write was used. Screens do not contain raw setup or invitation URL tokens.",
        "- The sample horse and stable images are the existing local `frontend/public/horse-panel.jpg` and `frontend/public/stable-panel.jpg`; no identifying person or facility text appears in either image. Upload examples use no real files.",
        "- Unknown `/api/v1` requests return an explicit `599 manual_fixture_missing` fixture error rather than being continued to the backend. The script fails at completion if an unknown request or handler error was observed.",
        "",
        f"Isolated CDP page target: `{target_id}`. Browser-fixture API replies: {len(api.seen)} requests; intercepted non-GET requests: {len(api.write_requests)} (all fulfilled in the browser, not sent to the backend).",
        "",
        "## Captured screens",
        "",
        "| Manual topic ID | Asset | Route and visible state | Source |",
        "|---|---|---|---|",
    ]
    for item in captures:
        lines.append(
            f"| `{item['topic']}` | `frontend/public/manual/{item['file']}` | "
            f"`{item['route']}` — {item['state']} | {item['source']} |"
        )
    lines.extend([
        "",
        "The screenshot mapping is exported as `adminScreenshots` from `frontend/src/pages/admin/manual/adminScreenshots.ts`. Only topic IDs with at least one genuine capture are included.",
        "",
        "## Reproduction",
        "",
        "Run from the repository root with the frontend already available at port 5000 and the normal `REPLIT_DEV_DOMAIN` environment variable set:",
        "",
        "```sh",
        "python scripts/capture-manual-admin.py",
        "```",
        "",
        "The script uses only standard Python modules plus the existing `websockets` package and Chromium from PATH; `cwebp` is used when available to compress final PNG captures as WebP. It creates and removes its own Chromium profile and does not start or restart the application.",
        "",
    ])
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    global BASE_URL
    parser = argparse.ArgumentParser(description="Capture synthetic admin manual screenshots.")
    parser.add_argument(
        "--only-email-logs",
        action="store_true",
        help="Refresh only the read-only Email Logs screenshots without rewriting the full manifest.",
    )
    arguments = parser.parse_args()
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "").strip()
    if not domain:
        raise RuntimeError("REPLIT_DEV_DOMAIN is not set; the script refuses to guess a frontend origin.")
    BASE_URL = f"https://{domain}".rstrip("/")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = FixtureAPI()
    target, process, profile = await create_target()
    cdp = CDP(target.websocket_url, fixtures)
    captures: list[dict[str, str]] = []
    try:
        await cdp.connect()
        await cdp.command(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": WIDTH,
                "height": HEIGHT,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        await cdp.command("Network.enable")
        captures = (
            await create_email_log_captures(cdp)
            if arguments.only_email_logs
            else await create_captures(cdp)
        )
        await cdp.command("Page.disable")
    finally:
        await cdp.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)

    if fixtures.unknown:
        raise RuntimeError("Unknown requests were blocked by fixtures:\n" + "\n".join(fixtures.unknown))
    if fixtures.failures:
        raise RuntimeError("Fixture handling errors:\n" + "\n".join(fixtures.failures))
    if cdp.page_errors:
        raise RuntimeError("Browser JavaScript exceptions:\n" + "\n".join(cdp.page_errors[:20]))
    if cdp.console_errors:
        print("Browser console errors:", file=sys.stderr)
        for error in cdp.console_errors[:20]:
            print(f"  {error}", file=sys.stderr)

    if not arguments.only_email_logs:
        write_provenance(captures, fixtures, target.id)
    print(f"Captured {len(captures)} admin screenshots.")
    print(f"Intercepted {len(fixtures.seen)} API requests, including {len(fixtures.write_requests)} browser-only writes.")
    print(f"Assets: {ASSET_DIR.relative_to(ROOT)}")
    if arguments.only_email_logs:
        print(f"Email Logs refresh CDP target: {target.id}.")
        print("Full screenshot mapping and provenance remain unchanged.")
    else:
        print(f"Provenance: {DOC_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))