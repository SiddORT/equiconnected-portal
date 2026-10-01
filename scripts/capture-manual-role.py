"""Capture genuine role-based User Manual screens from the running app.

Every /api/v1 request is fulfilled from isolated synthetic fixtures. Unknown
API routes fail closed with an explicit fixture error; no application API
request is allowed to reach the backend. The app's static React/CSS/image
modules continue to load from the running frontend.
"""

import asyncio
import base64
import copy
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import websockets
from PIL import Image
from io import BytesIO


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "manual"
CHROMIUM = "/repl/tools/bin/chromium"
CDP_PORT = 9242
PROFILE_DIR = Path("/tmp/equiconnected-manual-role-chromium")
TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")
SAMPLE_EMAIL = "sample.member@example.test"
PROVIDER_EMAIL = "sample.provider@example.test"
PROVIDER_NAME = "Sample Meadow Equine Clinic"
PHOTO_URL = "/horse-panel.jpg"
SAMPLE_TOKEN = "sample-only-invitation-token"
ASSET_NAMES = {
    "role-member-registration": "member-create-account",
    "role-member-verification-handoff": "member-create-account-verification",
    "role-member-verification-complete": "member-create-account-verified",
    "role-member-sign-in": "member-sign-in",
    "role-member-signed-in": "member-sign-in-success",
    "role-provider-registration": "provider-public-registration",
    "role-provider-verification-handoff": "provider-public-registration-verification",
    "role-provider-verification-complete": "provider-public-registration-verified",
    "role-provider-password-setup": "provider-password-access-setup",
    "role-provider-password-ready": "provider-password-access-setup-complete",
    "role-provider-password-recovery": "provider-password-access-recovery",
    "role-provider-password-recovered": "provider-password-access-recovery-complete",
    "role-provider-access-guard": "troubleshoot-provider-portal-access",
    "role-provider-signin-form": "provider-sign-in",
    "role-provider-signed-in": "provider-sign-in-success",
    "role-invitation-profile": "provider-invitation-draft-submit-profile",
    "role-invitation-draft-saved": "provider-invitation-draft-submit-draft",
    "role-invitation-submitted": "provider-invitation-draft-submit",
    "role-provider-account-basic": "provider-profile-edit",
    "role-provider-account-professional": "provider-profile-edit-professional",
    "role-provider-account-services": "provider-profile-edit-services",
    "role-provider-account-contacts": "provider-locations-contact",
    "role-provider-account-photos": "provider-profile-photos",
    "role-provider-photo-uploaded": "provider-profile-photos-uploaded",
    "role-provider-update-pending": "provider-profile-edit-pending-review",
    "role-provider-update-rejected": "provider-profile-edit-revision-requested",
    "role-provider-update-discarded": "provider-profile-edit-discarded",
    "role-provider-member-feedback": "provider-read-member-feedback",
    "role-provider-visits-history": "provider-visiting-schedule",
    "role-provider-trip-proposal": "provider-visiting-schedule-proposed-trip",
    "role-member-directory": "member-provider-directory",
    "role-member-directory-filters": "member-provider-directory-filters",
    "role-member-directory-location": "member-provider-directory-location",
    "role-member-directory-saved": "member-save-providers",
    "role-member-saved-providers": "member-save-providers-list",
    "role-member-provider-detail": "member-provider-profile-contact-photos",
    "role-member-provider-gallery": "member-provider-profile-contact-photos-gallery",
    "role-member-provider-locations": "member-provider-profile-contact-photos-locations",
    "role-member-review-form": "member-provider-reviews",
    "role-member-review-pending": "member-provider-reviews-pending",
    "role-member-visiting-calendar": "member-visiting-calendar",
    "role-member-profile": "member-personal-profile",
    "role-member-stable-profile": "member-stable-profile",
    "role-member-horse-history": "member-horse-profiles",
    "role-member-private-history": "member-browsing-history",
    "role-member-review-moderation": "member-reviews-feedback-management",
    "role-member-review-edit": "member-provider-reviews-edit",
    "role-member-review-resubmitted": "member-provider-reviews-resubmitted",
    "role-member-private-feedback": "member-reviews-feedback-management-feedback",
    "role-member-feedback-compose": "member-private-feedback",
    "role-member-feedback-submitted": "member-private-feedback-submitted",
    "role-member-messages-inbox": "member-private-messages-inbox",
    "role-member-messages-start": "member-private-messages-start",
    "role-member-messages-started": "member-private-messages-started",
    "role-member-messages-thread": "member-private-messages-thread",
    "role-member-messages-replied": "member-private-messages-replied",
    "role-provider-messages-inbox": "provider-private-messages-inbox",
    "role-provider-messages-thread": "provider-private-messages-thread",
    "role-provider-messages-replied": "provider-private-messages-replied",
    "role-provider-insights-overview": "provider-insights-overview",
    "role-provider-insights-filtered": "provider-insights-filtered",
    "role-provider-insights-refreshed": "provider-insights-refreshed",
}


def photo(reference, alt, caption, order=0, thumbnail=False):
    return {
        "storage_reference": reference,
        "alt_text": alt,
        "caption": caption,
        "display_order": order,
        "is_thumbnail": thumbnail,
    }


def location(name, address, city, primary=False):
    return {
        "name": name,
        "address_line_1": address,
        "address_line_2": None,
        "city": city,
        "state_province": "California",
        "country": "United States",
        "postal_code": "90012",
        "latitude": None,
        "longitude": None,
        "is_primary": primary,
    }


def visit(visit_id, start, end, city):
    return {
        "id": visit_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "location": {
            "name": "Sample visiting clinic",
            "address_line_1": "100 Sample Care Lane",
            "address_line_2": None,
            "city": city,
            "state_province": "California",
            "country": "United States",
            "postal_code": "90012",
            "latitude": None,
            "longitude": None,
            "is_primary": False,
        },
    }


APPROVED_PHOTOS = [
    photo(
        PHOTO_URL,
        "Sample horse standing in a grassy field",
        "A quiet moment at the sample equine clinic",
        0,
        True,
    ),
    photo(
        PHOTO_URL,
        "Sample horse outdoors in soft evening light",
        "A welcoming care environment",
        1,
    ),
]

VISITS = [
    visit("sample-visit-previous", TODAY - timedelta(days=30), TODAY - timedelta(days=29), "Sample Valley"),
    visit("sample-visit-current", TODAY - timedelta(days=1), TODAY + timedelta(days=1), "Sample Grove"),
    visit("sample-visit-upcoming", TODAY + timedelta(days=8), TODAY + timedelta(days=9), "Sample Harbor"),
]

PROFILE = {
    "id": "sample-provider-id",
    "name": PROVIDER_NAME,
    "description": "Sample equine medicine, preventive care, and rehabilitation.",
    "email": PROVIDER_EMAIL,
    "phone": "+1 555 010 0200",
    "website": None,
    "visit_stability": "NOT_STABLE_VISIT",
    "maximum_working_radius_km": None,
    "emergency_services_available": True,
    "emergency_contact_number": "+1 555 010 0201",
    "specializations": [
        {"id": "sample-spec-equine", "name": "Equine internal medicine", "is_active": True},
        {"id": "sample-spec-rehab", "name": "Sports medicine and rehabilitation", "is_active": True},
        {"id": "sample-spec-dentistry", "name": "Equine dentistry", "is_active": True},
    ],
    "locations": [location("Sample clinic", "100 Sample Care Lane", "Sample Grove", True)],
    "photos": copy.deepcopy(APPROVED_PHOTOS),
    "phones": [
        {"country_code": "+1", "number": "555 010 0200", "is_primary": True},
        {"country_code": "+1", "number": "555 010 0201", "is_primary": False},
    ],
    "emails": [
        {"email": PROVIDER_EMAIL, "is_primary": True},
        {"email": "sample.office@example.test", "is_primary": False},
    ],
    "doctor_profile": None,
    "doctor_fields_available": True,
    "doctor_availability": "VISITING",
    "can_schedule_visits": True,
    "doctor_visits": copy.deepcopy(VISITS),
    "qualifications": [
        {
            "title": "Sample Doctor of Veterinary Medicine",
            "institution": "Sample Veterinary College",
            "year_obtained": 2014,
            "description": "Equine-focused clinical training.",
            "display_order": 0,
        },
        {
            "title": "Sample Equine Rehabilitation Certificate",
            "institution": "Sample Equine Institute",
            "year_obtained": 2018,
            "description": "Rehabilitation and return-to-work care.",
            "display_order": 1,
        },
    ],
    "average_rating": 4.8,
    "review_count": 16,
    "visible_reviews": [
        {
            "id": "sample-visible-review",
            "rating": 5,
            "comment": "Sample feedback: clear explanations and a thoughtful care plan.",
            "reviewer_name": "Sample Member",
            "created_at": "2026-06-02T12:00:00Z",
        }
    ],
    "editable_profile": {
        "name": PROVIDER_NAME,
        "description": "Sample equine medicine, preventive care, and rehabilitation.",
        "email": PROVIDER_EMAIL,
        "phone": "+1 555 010 0200",
        "website": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "maximum_working_radius_km": None,
        "emergency_services_available": True,
        "emergency_contact_number": "+1 555 010 0201",
        "specialization_ids": ["sample-spec-equine", "sample-spec-rehab"],
        "locations": [location("Sample clinic", "100 Sample Care Lane", "Sample Grove", True)],
        "phones": [
            {"country_code": "+1", "number": "555 010 0200", "is_primary": True},
            {"country_code": "+1", "number": "555 010 0201", "is_primary": False},
        ],
        "emails": [
            {"email": PROVIDER_EMAIL, "is_primary": True},
            {"email": "sample.office@example.test", "is_primary": False},
        ],
        "photos": copy.deepcopy(APPROVED_PHOTOS),
        "professional_title": "Sample Equine Veterinarian",
        "biography": "Sample practitioner focused on practical, evidence-led equine care.",
        "years_experience": 12,
        "experience_description": "Sample experience supporting horses through routine and referral care.",
        "visit_additions": [
            {
                "start_date": (TODAY + timedelta(days=18)).isoformat(),
                "end_date": (TODAY + timedelta(days=19)).isoformat(),
                "location": {
                    "name": "Sample outreach day",
                    "address_line_1": "200 Sample Field Road",
                    "address_line_2": None,
                    "city": "Sample Harbor",
                    "state_province": "California",
                    "country": "United States",
                    "postal_code": "90014",
                },
            }
        ],
        "qualifications": [
            {
                "title": "Sample Doctor of Veterinary Medicine",
                "institution": "Sample Veterinary College",
                "year_obtained": 2014,
                "description": "Equine-focused clinical training.",
                "display_order": 0,
            }
        ],
    },
    "profile_update": None,
}

MEMBER_PROFILE = {
    "first_name": "Sample",
    "last_name": "Rider",
    "email": SAMPLE_EMAIL,
    "mobile_number": "+1 555 010 0400",
    "address": "10 Sample Trail",
    "address_line_2": None,
    "country": "United States",
    "state_province": "California",
    "city": "Sample Grove",
    "postal_code": "90012",
    "roles": ["horse_owner", "stable_manager"],
    "stable_profile": {
        "name": "Sample Meadow Stable",
        "description": "Sample community stable focused on thoughtful horse care.",
        "address": "20 Sample Paddock Road",
        "address_line_2": None,
        "country": "United States",
        "state_province": "California",
        "city": "Sample Valley",
        "postal_code": "90013",
        "contact_name": "Sample Stable Contact",
        "contact_phone": "+1 555 010 0401",
        "contact_email": "sample.stable@example.test",
    },
    "horses": [
        {
            "id": "sample-horse-id",
            "name": "Sample Comet",
            "sex": "GELDING",
            "registered_name": "Sample Comet",
            "breed": "Sample Sport Horse",
            "date_of_birth": "2018-04-14",
            "color": "Bay",
            "primary_discipline": "Dressage",
            "registration_number": None,
            "microchip_number": None,
            "description": "Sample horse profile for demonstration only.",
            "photo_reference": PHOTO_URL,
        }
    ],
}

PROVIDER_LIST = [
    {
        "id": "sample-clinic-id",
        "is_saved": False,
        "provider_type": "CLINIC",
        "name": "Sample Meadow Equine Clinic",
        "description": "Sample general and referral equine care.",
        "thumbnail_url": PHOTO_URL,
        "thumbnail_alt_text": "Sample horse standing in a grassy field",
        "website": None,
        "email": "sample.clinic@example.test",
        "phone": "+1 555 010 0500",
        "visit_stability": "STABLE_VISIT",
        "location": {
            "name": "Sample clinic",
            "city": "Sample Grove",
            "state_province": "California",
            "country": "United States",
        },
        "average_rating": 4.8,
        "review_count": 16,
        "distance_km": 4.2,
        "specializations": ["Equine internal medicine", "Sports medicine and rehabilitation"],
        "emergency_services_available": True,
    },
    {
        "id": "sample-doctor-id",
        "is_saved": True,
        "provider_type": "DOCTOR",
        "name": "Sample Visiting Veterinarian",
        "description": "Sample visiting equine care and routine consultations.",
        "thumbnail_url": PHOTO_URL,
        "thumbnail_alt_text": "Sample horse outdoors in soft evening light",
        "website": None,
        "email": "sample.doctor@example.test",
        "phone": "+1 555 010 0600",
        "visit_stability": "NOT_STABLE_VISIT",
        "location": {
            "name": "Sample mobile service",
            "city": "Sample Valley",
            "state_province": "California",
            "country": "United States",
        },
        "average_rating": 4.6,
        "review_count": 9,
        "distance_km": 8.6,
        "specializations": ["Equine dentistry", "Preventive care"],
        "emergency_services_available": False,
    },
    {
        "id": "sample-hospital-id",
        "is_saved": False,
        "provider_type": "HOSPITAL",
        "name": "Sample Valley Equine Hospital",
        "description": "Sample hospital services and referral support.",
        "thumbnail_url": PHOTO_URL,
        "thumbnail_alt_text": "Sample horse at a peaceful care setting",
        "website": None,
        "email": "sample.hospital@example.test",
        "phone": "+1 555 010 0700",
        "visit_stability": "NOT_STABLE_VISIT",
        "location": {
            "name": "Sample hospital",
            "city": "Sample Harbor",
            "state_province": "California",
            "country": "United States",
        },
        "average_rating": 4.9,
        "review_count": 24,
        "distance_km": 12.1,
        "specializations": ["Emergency and critical care", "Equine surgery"],
        "emergency_services_available": True,
    },
]

PROVIDER_DETAIL = {
    **copy.deepcopy(PROVIDER_LIST[0]),
    "id": "sample-clinic-id",
    "name": "Sample Meadow Equine Clinic",
    "years_experience": 12,
    "professional_title": "Sample Equine Veterinarian",
    "biography": "Sample equine clinicians offer clear, collaborative care for horses and the people who care for them.",
    "experience_description": "Sample experience in preventive care, internal medicine, and rehabilitation.",
    "qualifications": copy.deepcopy(PROFILE["qualifications"]),
    "photos": [
        {
            "url": PHOTO_URL,
            "alt_text": "Sample horse standing in a grassy field",
            "caption": "A quiet moment at the sample equine clinic",
            "display_order": 0,
            "is_thumbnail": True,
        },
        {
            "url": PHOTO_URL,
            "alt_text": "Sample horse outdoors in soft evening light",
            "caption": "A welcoming care environment",
            "display_order": 1,
            "is_thumbnail": False,
        },
    ],
    "languages": [{"name": "English", "code": "en"}, {"name": "Spanish", "code": "es"}],
    "locations": [
        {
            "name": "Sample clinic",
            "address_line_1": "100 Sample Care Lane",
            "city": "Sample Grove",
            "state_province": "California",
            "country": "United States",
            "postal_code": "90012",
            "is_primary": True,
        },
        {
            "name": "Sample outreach location",
            "address_line_1": "200 Sample Field Road",
            "city": "Sample Harbor",
            "state_province": "California",
            "country": "United States",
            "postal_code": "90014",
            "is_primary": False,
        },
    ],
    "maximum_working_radius_km": 35,
    "clinic_hospital_visit": True,
    "doctor_availability": "VISITING",
    "doctor_visits": [
        {
            "start_date": (TODAY + timedelta(days=8)).isoformat(),
            "end_date": (TODAY + timedelta(days=9)).isoformat(),
            "location": {
                "city": "Sample Harbor",
                "state_province": "California",
                "country": "United States",
            },
        }
    ],
    "visible_reviews": [
        {
            "id": "sample-review-published",
            "rating": 5,
            "comment": "Sample review: the care team explained each option clearly.",
            "reviewer_name": "Sample Member",
            "created_at": "2026-06-02T12:00:00Z",
        },
        {
            "id": "sample-review-second",
            "rating": 4,
            "comment": "Sample review: convenient scheduling and kind follow-up.",
            "reviewer_name": "Sample Stable Manager",
            "created_at": "2026-05-18T09:30:00Z",
        },
    ],
    "own_review": None,
}

MEMBER_REVIEW = {
    "id": "sample-member-review",
    "provider_id": "sample-clinic-id",
    "provider_name": "Sample Meadow Equine Clinic",
    "rating": 4,
    "comment": "Sample review: helpful communication and practical next steps.",
    "status": "REJECTED",
    "member_note": "Sample moderator note: please keep the review focused on your own experience.",
    "created_at": "2026-06-10T12:00:00Z",
    "updated_at": "2026-06-10T12:00:00Z",
    "version": 1,
}

PLATFORM_FEEDBACK = {
    "id": "sample-feedback-id",
    "category": "Search & Matching",
    "subject": "Sample search feedback",
    "rating": 4,
    "message": "Sample private feedback: the specialty filters were easy to use.",
    "status": "In review",
    "member_response": None,
    "submitted_at": "2026-06-12T12:00:00Z",
    "updated_at": "2026-06-12T12:00:00Z",
    "version": 1,
    "withdrawn_at": None,
}

INVITATION = {
    "id": "sample-invitation-id",
    "provider_type": "CLINIC",
    "recipient_email": "sample.invited@example.test",
    "emails_edited": False,
    "provider": {
        "name": "Sample Invited Equine Clinic",
        "first_name": "Sample",
        "last_name": "Applicant",
        "description": "Sample clinic profile draft for invited provider onboarding.",
        "email": "sample.invited@example.test",
        "phone": "+1 555 010 0800",
        "website": None,
        "visit_stability": "NOT_STABLE_VISIT",
        "maximum_working_radius_km": None,
        "emergency_services_available": False,
        "emergency_contact_number": None,
        "status": "ACTIVE",
        "specialization_ids": ["sample-spec-equine"],
        "language_ids": ["sample-lang-en"],
        "locations": [location("Sample clinic", "300 Sample Orchard Way", "Sample Valley", True)],
        "phones": [{"country_code": "+1", "number": "555 010 0800", "is_primary": True}],
        "emails": [{"email": "sample.invited@example.test", "is_primary": True}],
        "photos": copy.deepcopy(APPROVED_PHOTOS[:1]),
        "professional_title": "Sample Equine Veterinarian",
        "biography": "Sample invited provider introduction.",
        "years_experience": 8,
        "experience_description": "Sample experience in equine medicine and preventative care.",
    },
}

SAMPLE_MESSAGE_CONVERSATION_ID = "sample-private-conversation"
SAMPLE_MESSAGE_CONTACT = {
    "name": "Sample Rider",
    "email": SAMPLE_EMAIL,
    "phone": "+1 555 010 0400",
}
SAMPLE_MESSAGES = [
    {
        "id": "sample-private-message-1",
        "sequence": 1,
        "sender_side": "member",
        "created_at": "2026-06-12T16:00:00Z",
        "body": "Sample member message: Hello, could you share what routine visit options may be available next week?",
    },
    {
        "id": "sample-private-message-2",
        "sequence": 2,
        "sender_side": "provider",
        "created_at": "2026-06-12T17:00:00Z",
        "body": "Sample provider reply: Thank you for reaching out. We can discuss available visit times for next week.",
    },
]

SPECS = [
    {"id": "sample-spec-equine", "name": "Equine internal medicine"},
    {"id": "sample-spec-rehab", "name": "Sports medicine and rehabilitation"},
    {"id": "sample-spec-dentistry", "name": "Equine dentistry"},
]
LANGUAGES = [
    {"id": "sample-lang-en", "name": "English", "code": "en"},
    {"id": "sample-lang-es", "name": "Spanish", "code": "es"},
]


class Fixtures:
    def __init__(self):
        self.role = "member"
        self.unauthenticated = False
        self.provider_profile = copy.deepcopy(PROFILE)
        self.member_profile = copy.deepcopy(MEMBER_PROFILE)
        self.member_providers = copy.deepcopy(PROVIDER_LIST)
        self.detail = copy.deepcopy(PROVIDER_DETAIL)
        self.member_review = copy.deepcopy(MEMBER_REVIEW)
        self.feedback = copy.deepcopy(PLATFORM_FEEDBACK)
        self.invitation = copy.deepcopy(INVITATION)
        self.message_conversations = {
            SAMPLE_MESSAGE_CONVERSATION_ID: {
                "conversation": {
                    "id": SAMPLE_MESSAGE_CONVERSATION_ID,
                    "provider_id": "sample-clinic-id",
                    "provider_name": PROVIDER_NAME,
                    "member_name": "Sample Rider",
                    "last_message_at": SAMPLE_MESSAGES[-1]["created_at"],
                    "unread_count": 0,
                    "last_sequence": len(SAMPLE_MESSAGES),
                    "notifications_failed": False,
                },
                "messages": copy.deepcopy(SAMPLE_MESSAGES),
            }
        }
        self.message_read_sequences = {"member": {}, "provider": {}}
        self.next_message_conversation = 0
        self.message_requests = {}
        self.provider_insights_requests = 0
        self.unknown = []
        self.api_requests = []
        self.fixture_failure = None

    def reset_message_conversations(self):
        self.message_conversations = {
            SAMPLE_MESSAGE_CONVERSATION_ID: {
                "conversation": {
                    "id": SAMPLE_MESSAGE_CONVERSATION_ID,
                    "provider_id": "sample-clinic-id",
                    "provider_name": PROVIDER_NAME,
                    "member_name": "Sample Rider",
                    "last_message_at": SAMPLE_MESSAGES[-1]["created_at"],
                    "unread_count": 0,
                    "last_sequence": len(SAMPLE_MESSAGES),
                    "notifications_failed": False,
                },
                "messages": copy.deepcopy(SAMPLE_MESSAGES),
            }
        }
        self.message_read_sequences = {"member": {}, "provider": {}}
        self.next_message_conversation = 0
        self.message_requests = {}

    def message_unread_sequences(self, conversation_id, role):
        conversation = self.message_conversations.get(conversation_id)
        if not conversation:
            return []
        read = self.message_read_sequences.setdefault(role, {}).setdefault(conversation_id, set())
        return [
            item["sequence"]
            for item in conversation["messages"]
            if item["sender_side"] != role and item["sequence"] not in read
        ]

    def message_summary(self, conversation_id, role):
        conversation = self.message_conversations[conversation_id]
        summary = copy.deepcopy(conversation["conversation"])
        summary["unread_count"] = len(self.message_unread_sequences(conversation_id, role))
        return summary

    def message_conversation_response(self, conversation_id, role):
        conversation = self.message_conversations.get(conversation_id)
        if not conversation:
            return None
        return {
            "conversation": self.message_summary(conversation_id, role),
            "messages": copy.deepcopy(conversation["messages"]),
            "contact": copy.deepcopy(SAMPLE_MESSAGE_CONTACT) if role == "provider" else None,
            "next_before_sequence": None,
            "unread_count": len(self.message_unread_sequences(conversation_id, role)),
        }

    def provider_insights_response(self, query):
        preset = query.get("preset", ["last_30_days"])[0]
        if preset not in {"last_7_days", "last_30_days", "this_month", "custom"}:
            return {"detail": {"message": "Sample insights period is invalid."}}, 422
        if preset == "custom":
            try:
                start = date.fromisoformat(query.get("date_from", [""])[0])
                end = date.fromisoformat(query.get("date_to", [""])[0])
            except ValueError:
                return {"detail": {"message": "Sample custom insights dates are invalid."}}, 422
            if start > end or end > TODAY or (end - start).days >= 366:
                return {"detail": {"message": "Sample custom insights dates are outside the supported range."}}, 422
        elif preset == "this_month":
            start = TODAY.replace(day=1)
            end = TODAY
        else:
            days = 7 if preset == "last_7_days" else 30
            end = TODAY
            start = end - timedelta(days=days - 1)

        self.provider_insights_requests += 1
        days = (end - start).days + 1
        coverage_start = TODAY - timedelta(days=12)
        trends = []
        for offset in range(days):
            point_date = start + timedelta(days=offset)
            trends.append({
                "date": point_date.isoformat(),
                "profile_views": 2 + (offset % 5),
                "contact_clicks": (offset % 4) + 1 if point_date >= coverage_start else None,
            })
        profile_views = sum(point["profile_views"] for point in trends)
        contact_values = [point["contact_clicks"] for point in trends if point["contact_clicks"] is not None]
        contact_clicks = sum(contact_values)
        partial_contact_coverage = start < coverage_start
        contact_start = max(start, coverage_start)
        new_conversations = max(1, days // 4)
        previous_views = max(1, round(profile_views / 1.12))
        previous_conversations = max(1, new_conversations - 1)
        refreshed_at = f"{TODAY.isoformat()}T16:{self.provider_insights_requests % 60:02d}:00Z"
        payload = {
            "provider_name": PROVIDER_NAME,
            "timezone": "UTC",
            "today": TODAY.isoformat(),
            "period": {
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
                "preset": preset,
            },
            "refreshed_at": refreshed_at,
            "metrics": {
                "profile_views": {
                    "value": profile_views,
                    "definition": "Successfully loaded member profile pages. Revisits count again; this is not a unique-person or appointment count.",
                    "coverage": {
                        "status": "full",
                        "from": (TODAY - timedelta(days=365)).isoformat(),
                        "note": "",
                    },
                    "comparison": {
                        "change_percent": round((profile_views - previous_views) / previous_views * 100, 1),
                        "previous_value": previous_views,
                        "reason": None,
                    },
                },
                "contact_clicks": {
                    "value": contact_clicks,
                    "definition": "Clicks on a listed phone, email, or website link; a click does not confirm a call or other outcome.",
                    "coverage": {
                        "status": "partial" if partial_contact_coverage else "full",
                        "from": contact_start.isoformat(),
                        "note": (
                            f"Contact-link collection began {coverage_start.isoformat()}; earlier days may be missing."
                            if partial_contact_coverage else ""
                        ),
                    },
                    "comparison": {
                        "change_percent": None if partial_contact_coverage else 8.3,
                        "previous_value": max(1, contact_clicks - 2),
                        "reason": "partial_coverage" if partial_contact_coverage else None,
                    },
                },
                "new_conversations": {
                    "value": new_conversations,
                    "definition": "Private conversations started by members during the selected period.",
                    "coverage": {
                        "status": "full",
                        "from": (TODAY - timedelta(days=365)).isoformat(),
                        "note": "",
                    },
                    "comparison": {
                        "change_percent": round(
                            (new_conversations - previous_conversations) / previous_conversations * 100,
                            1,
                        ),
                        "previous_value": previous_conversations,
                        "reason": None,
                    },
                },
            },
            "contact_breakdown": {
                "phone": contact_clicks // 2,
                "email": contact_clicks // 3,
                "website": contact_clicks - contact_clicks // 2 - contact_clicks // 3,
            },
            "snapshot": {
                "saved_members": 24,
                "rating_count": 19,
                "visible_review_count": 16,
                "average_rating": 4.8,
            },
            "trends": trends,
        }
        return payload, 200

    def user(self):
        role = self.role
        email = {
            "member": SAMPLE_EMAIL,
            "provider": PROVIDER_EMAIL,
            "admin": "sample.admin@example.test",
        }.get(role, SAMPLE_EMAIL)
        first, last = {
            "member": ("Sample", "Rider"),
            "provider": ("Sample", "Applicant"),
            "admin": ("Sample", "Administrator"),
        }.get(role, ("Sample", "Rider"))
        return {
            "id": f"sample-{role}-user",
            "email": email,
            "full_name": f"{first} {last}",
            "first_name": first,
            "last_name": last,
            "role": role,
            "roles": ["horse_owner", "stable_manager"] if role == "member" else [role],
            "is_active": True,
            "email_verified_at": "2026-06-01T12:00:00Z",
        }

    def reply(self, path, method, query, body):
        if path.endswith("/auth/refresh") or path.endswith("/auth/me"):
            if self.unauthenticated:
                return {"detail": {"message": "Sample session is not authenticated."}}, 401
            return {"access_token": "sample-only-session-token", "user": self.user()}, 200
        if path.endswith("/auth/login"):
            return {
                "access_token": "sample-only-session-token",
                "user": self.user(),
            }, 200
        if path.endswith("/system-settings"):
            return {"timezone": "America/Los_Angeles", "date_format": "month_day_year", "time_format": "12_hour"}, 200
        if path.endswith("/public/traffic/page-view") or path.endswith("/member/providers/traffic-view"):
            return {"recorded": True, "sample_fixture": True}, 201
        if path.endswith("/public/visits"):
            return {"recorded": True, "sample_fixture": True}, 201
        if path == "/api/v1/provider/portal/insights" and method == "GET":
            return self.provider_insights_response(query)
        if path == "/api/v1/messages/availability" and method == "GET":
            provider_id = query.get("provider_id", [""])[0]
            available = provider_id == "sample-clinic-id"
            return {
                "available": available,
                "reason": None if available else "provider_unavailable",
                "provider_name": PROVIDER_NAME if available else None,
            }, 200
        if path == "/api/v1/messages/unread" and method == "GET":
            count = sum(
                len(self.message_unread_sequences(conversation_id, self.role))
                for conversation_id in self.message_conversations
            )
            return {"count": count}, 200
        if path == "/api/v1/messages/inbox" and method == "GET":
            page = max(1, int(query.get("page", ["1"])[0]))
            page_size = max(1, int(query.get("page_size", ["20"])[0]))
            conversations = sorted(
                self.message_conversations,
                key=lambda conversation_id: self.message_conversations[conversation_id]["conversation"]["last_message_at"],
                reverse=True,
            )
            start = (page - 1) * page_size
            return {
                "items": [self.message_summary(conversation_id, self.role) for conversation_id in conversations[start:start + page_size]],
                "page": page,
                "page_size": page_size,
                "total": len(conversations),
            }, 200
        if path == "/api/v1/messages/start" and method == "POST":
            if body.get("consent") is not True or body.get("provider_id") != "sample-clinic-id":
                return {"detail": {"message": "Sample messaging consent or provider selection is invalid."}}, 422
            request_id = body.get("request_id")
            if not isinstance(request_id, str) or not request_id or not isinstance(body.get("message"), str):
                return {"detail": {"message": "Sample message request is invalid."}}, 422
            if request_id in self.message_requests:
                return copy.deepcopy(self.message_requests[request_id]), 201
            self.next_message_conversation += 1
            conversation_id = f"sample-started-conversation-{self.next_message_conversation}"
            created_at = f"{TODAY.isoformat()}T15:30:00Z"
            initial_message = {
                "id": f"sample-started-message-{self.next_message_conversation}",
                "sequence": 1,
                "sender_side": "member",
                "created_at": created_at,
                "body": body["message"].strip(),
            }
            self.message_conversations[conversation_id] = {
                "conversation": {
                    "id": conversation_id,
                    "provider_id": "sample-clinic-id",
                    "provider_name": PROVIDER_NAME,
                    "member_name": "Sample Rider",
                    "last_message_at": created_at,
                    "unread_count": 0,
                    "last_sequence": 1,
                    "notifications_failed": False,
                },
                "messages": [initial_message],
            }
            response = self.message_conversation_response(conversation_id, self.role)
            self.message_requests[request_id] = copy.deepcopy(response)
            return response, 201
        if path.startswith("/api/v1/messages/") and path.endswith("/messages") and method == "POST":
            conversation_id = path.split("/")[-2]
            conversation = self.message_conversations.get(conversation_id)
            request_id = body.get("request_id")
            message_text = body.get("message")
            if not conversation:
                return {"detail": {"message": "Sample conversation was not found."}}, 404
            if not isinstance(request_id, str) or not request_id or not isinstance(message_text, str) or not message_text.strip():
                return {"detail": {"message": "Sample message request is invalid."}}, 422
            if request_id in self.message_requests:
                return copy.deepcopy(self.message_requests[request_id]), 201
            sequence = conversation["conversation"]["last_sequence"] + 1
            created_at = f"{TODAY.isoformat()}T15:{(30 + sequence) % 60:02d}:00Z"
            sent_message = {
                "id": f"sample-private-message-{conversation_id}-{sequence}",
                "sequence": sequence,
                "sender_side": self.role,
                "created_at": created_at,
                "body": message_text.strip(),
            }
            conversation["messages"].append(sent_message)
            conversation["conversation"]["last_sequence"] = sequence
            conversation["conversation"]["last_message_at"] = created_at
            self.message_requests[request_id] = copy.deepcopy(sent_message)
            return sent_message, 201
        if path.startswith("/api/v1/messages/") and path.endswith("/read") and method == "POST":
            conversation_id = path.split("/")[-2]
            conversation = self.message_conversations.get(conversation_id)
            if not conversation:
                return {"detail": {"message": "Sample conversation was not found."}}, 404
            requested_sequences = body.get("message_sequences", [])
            if not isinstance(requested_sequences, list):
                return {"detail": {"message": "Sample read receipt is invalid."}}, 422
            incoming = {
                item["sequence"]
                for item in conversation["messages"]
                if item["sender_side"] != self.role
            }
            read_sequences = sorted(
                sequence for sequence in requested_sequences
                if isinstance(sequence, int) and sequence in incoming
            )
            receipts = self.message_read_sequences.setdefault(self.role, {}).setdefault(conversation_id, set())
            receipts.update(read_sequences)
            return {
                "read_sequence": max(read_sequences, default=0),
                "read_sequences": read_sequences,
            }, 200
        if path.startswith("/api/v1/messages/") and method == "GET":
            conversation_id = path.rsplit("/", 1)[-1]
            response = self.message_conversation_response(conversation_id, self.role)
            if response is None:
                return {"detail": {"message": "Sample conversation was not found."}}, 404
            before_sequence = query.get("before_sequence", [None])[0]
            limit = max(1, int(query.get("limit", ["50"])[0]))
            messages = response["messages"]
            if before_sequence:
                messages = [item for item in messages if item["sequence"] < int(before_sequence)]
            if len(messages) > limit:
                messages = messages[-limit:]
            response["messages"] = messages
            response["next_before_sequence"] = messages[0]["sequence"] - 1 if messages and messages[0]["sequence"] > 1 else None
            return response, 200
        if path.endswith("/member/history") or path.endswith("/member/history/recent"):
            search_entry = {
                "id": "sample-history-search",
                "event_key": "sample-search-event",
                "type": "search",
                "occurred_at": "2026-06-14T11:45:00Z",
                "filters": {"region": "Sample Grove", "specialization_id": "sample-spec-equine", "sort": "relevance"},
                "provider_id": None,
                "provider_name": None,
                "provider_available": None,
            }
            provider_entry = {
                "id": "sample-history-provider",
                "event_key": "sample-provider-event",
                "type": "provider",
                "occurred_at": "2026-06-14T11:30:00Z",
                "filters": None,
                "provider_id": "sample-clinic-id",
                "provider_name": "Sample Meadow Equine Clinic",
                "provider_available": True,
            }
            if path.endswith("/recent"):
                return [search_entry, provider_entry], 200
            return {"data": [search_entry, provider_entry], "meta": {"page": 1, "page_size": 10, "total": 2, "total_pages": 1}}, 200
        if path.endswith("/auth/register") or path.endswith("/auth/provider-register"):
            return {"message": "Sample verification handoff.", "email_sent": True}, 201
        if path.endswith("/auth/provider-specializations"):
            return SPECS, 200
        if path.endswith("/auth/provider-languages"):
            return LANGUAGES, 200
        if path.endswith("/auth/verify-email"):
            return {
                "message": "Sample email verification is complete. You can sign in.",
                "email": SAMPLE_EMAIL if body.get("token") == "sample-member-verification" else "sample.provider@example.test",
                "redirect_to": "/login" if body.get("token") == "sample-member-verification" else "/provider/login",
            }, 200
        if path.endswith("/auth/provider-portal/setup-password") or path.endswith("/auth/provider-portal/reset-password"):
            return {"message": "Sample password setup complete."}, 200
        if path.endswith("/provider/portal/profile"):
            if method == "GET":
                return copy.deepcopy(self.provider_profile), 200
            if method == "PATCH":
                for key, value in body.items():
                    if key in self.provider_profile["editable_profile"]:
                        self.provider_profile["editable_profile"][key] = copy.deepcopy(value)
                for key in ("name", "description", "email", "phone", "website", "visit_stability", "maximum_working_radius_km", "emergency_services_available", "emergency_contact_number"):
                    if key in body:
                        self.provider_profile[key] = copy.deepcopy(body[key])
                self.provider_profile["locations"] = copy.deepcopy(body.get("locations", self.provider_profile["editable_profile"]["locations"]))
                self.provider_profile["photos"] = copy.deepcopy(body.get("photos", self.provider_profile["editable_profile"]["photos"]))
                self.provider_profile["profile_update"] = {
                    "id": "sample-provider-update",
                    "review_status": "PENDING_REVIEW",
                    "submitted_at": "2026-06-14T12:00:00Z",
                    "reviewed_at": None,
                    "reviewed_by_name": None,
                    "rejection_reason": None,
                }
                return copy.deepcopy(self.provider_profile), 200
        if path.endswith("/provider/portal/profile-update/discard"):
            self.provider_profile = copy.deepcopy(PROFILE)
            return copy.deepcopy(self.provider_profile), 200
        if path.endswith("/provider/portal/specializations"):
            return SPECS, 200
        if path.endswith("/provider/portal/profile/photos/upload"):
            count = len(self.provider_profile["editable_profile"]["photos"])
            uploaded = photo(
                PHOTO_URL,
                "Sample uploaded horse photo",
                "Sample uploaded care-setting image",
                count,
                count == 0,
            )
            return uploaded, 201
        if path.endswith("/member/providers/filters"):
            return {
                "specializations": SPECS,
                "regions": ["Sample Grove", "Sample Harbor", "Sample Valley"],
            }, 200
        if path.endswith("/member/providers/visits/availability"):
            return {"has_visits": True}, 200
        if path.endswith("/member/providers/visits/calendar"):
            requested = query.get("month", [MONTH])[0] or MONTH
            sample_visits = [
                {
                    "id": "sample-calendar-visit",
                    "provider_id": "sample-doctor-id",
                    "provider_name": "Sample Visiting Veterinarian",
                    "start_date": (TODAY + timedelta(days=8)).isoformat(),
                    "end_date": (TODAY + timedelta(days=9)).isoformat(),
                    "specializations": ["Equine dentistry", "Preventive care"],
                    "location": {"city": "Sample Harbor", "state_province": "California", "country": "United States"},
                }
            ] if requested == MONTH else []
            return {"month": requested, "today": TODAY.isoformat(), "visits": sample_visits}, 200
        if path.rstrip("/") == "/api/v1/member/providers":
            rows = copy.deepcopy(self.member_providers)
            params = {key: values[-1] for key, values in query.items()}
            if params.get("saved_only") == "true":
                rows = [row for row in rows if row["is_saved"]]
            search = params.get("name", "").lower()
            if search:
                rows = [row for row in rows if search in row["name"].lower()]
            return {
                "data": rows,
                "meta": {"page": int(params.get("page", "1")), "page_size": int(params.get("page_size", "10")), "total": len(rows), "total_pages": max(1, (len(rows) + 9) // 10)},
            }, 200
        if path.endswith("/member/providers/sample-clinic-id/favorite") or path.endswith("/member/providers/sample-doctor-id/favorite"):
            provider_id = path.split("/")[-2]
            for item in self.member_providers:
                if item["id"] == provider_id:
                    item["is_saved"] = method == "PUT"
            return {"saved": method == "PUT"}, 200
        if path.endswith("/member/providers/sample-clinic-id/review"):
            self.detail["own_review"] = {
                "id": "sample-detail-review",
                "rating": body.get("rating", 5),
                "comment": body.get("comment", ""),
                "status": "PENDING",
                "comment_visible": False,
                "version": 2,
                "member_note": None,
            }
            return copy.deepcopy(self.detail["own_review"]), 200
        if path.rstrip("/") == "/api/v1/member/providers/sample-clinic-id":
            return copy.deepcopy(self.detail), 200
        if path.endswith("/profile"):
            return copy.deepcopy(self.member_profile), 200
        if path.endswith("/profile/personal"):
            self.member_profile.update(body)
            return copy.deepcopy(self.member_profile), 200
        if path.endswith("/profile/stable"):
            self.member_profile["stable_profile"].update(body)
            return copy.deepcopy(self.member_profile["stable_profile"]), 200
        if path.endswith("/profile/horses"):
            horse = {"id": "sample-horse-new", **body, "photo_reference": None}
            self.member_profile["horses"].append(horse)
            return horse, 201
        if path.rstrip("/").endswith("/profile/horses/sample-horse-id"):
            self.member_profile["horses"][0].update(body)
            return copy.deepcopy(self.member_profile["horses"][0]), 200
        if "/profile/horses/" in path:
            return {}, 204
        if path.endswith("/member/reviews/counts"):
            return {"all": 1, "pending": 0, "published": 0, "rejected": 1, "hidden": 0}, 200
        if path.endswith("/member/feedback/counts"):
            return {"total": 1, "pending": 0, "in_review": 1, "resolved": 0, "rejected": 0}, 200
        if path.rstrip("/") == "/api/v1/member/reviews":
            return {"data": [copy.deepcopy(self.member_review)], "meta": {"page": 1, "page_size": 6, "total": 1, "total_pages": 1}}, 200
        if path.rstrip("/") == "/api/v1/member/feedback":
            if method == "POST":
                self.feedback = {
                    "id": "sample-feedback-created",
                    **body,
                    "status": "Pending",
                    "member_response": None,
                    "submitted_at": "2026-06-14T12:00:00Z",
                    "updated_at": "2026-06-14T12:00:00Z",
                    "version": 1,
                    "withdrawn_at": None,
                }
                return copy.deepcopy(self.feedback), 201
            return {"data": [copy.deepcopy(self.feedback)], "meta": {"page": 1, "page_size": 6, "total": 1, "total_pages": 1}}, 200
        if path.rstrip("/") == "/api/v1/member/reviews/sample-member-review" and method == "PUT":
            self.member_review.update(body, status="PENDING", member_note=None, version=2)
            return copy.deepcopy(self.member_review), 200
        if path.rstrip("/") == "/api/v1/member/reviews/sample-member-review" and method == "DELETE":
            return {}, 204
        if path.rstrip("/") == "/api/v1/member/feedback/sample-feedback-id" and method == "PATCH":
            self.feedback.update(body, status="Pending", version=2)
            return copy.deepcopy(self.feedback), 200
        if path.rstrip("/") == "/api/v1/member/feedback/sample-feedback-id" and method == "DELETE":
            return {}, 204
        if path.rstrip("/") == "/api/v1/provider/invitations/sample-only-invitation-token":
            return copy.deepcopy(self.invitation), 200
        if path.endswith("/provider/invitations/sample-only-invitation-token/specializations"):
            return {"data": SPECS}, 200
        if path.endswith("/provider/invitations/sample-only-invitation-token/save"):
            self.invitation["provider"].update(body)
            return copy.deepcopy(self.invitation), 200
        if path.endswith("/provider/invitations/sample-only-invitation-token/submit"):
            self.invitation["provider"].update(body)
            return copy.deepcopy(self.invitation), 200
        if path.endswith("/provider/organizations/search"):
            return {"data": [], "meta": {"page": 1, "page_size": 10, "total": 0, "total_pages": 1}}, 200
        if path.startswith("/api/v1/"):
            self.unknown.append({"path": path, "method": method})
            return {
                "detail": {
                    "code": "manual_fixture_missing",
                    "message": f"Sample browser fixture missing for {method} {path}; request blocked.",
                }
            }, 501
        return None, 0


FIXTURES = Fixtures()


async def main(provider_refresh=False):
    domain = os.environ.get("REPLIT_DEV_DOMAIN")
    if not domain:
        raise RuntimeError("REPLIT_DEV_DOMAIN is required to use the already-running frontend.")
    OUT.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome = subprocess.Popen(
        [
            CHROMIUM,
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--ignore-certificate-errors",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={PROFILE_DIR}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        targets = None
        for _ in range(120):
            try:
                targets = json.load(urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=1))
                break
            except Exception:
                if chrome.poll() is not None:
                    raise RuntimeError("Dedicated Chromium exited before its CDP endpoint became ready.")
                await asyncio.sleep(0.25)
        if targets is None:
            raise RuntimeError(f"Dedicated Chromium did not open its CDP endpoint on {CDP_PORT}.")
        target = next((item for item in targets if item.get("type") == "page"), None)
        if not target:
            raise RuntimeError("Dedicated Chromium did not expose a target of type page.")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
            pending = {}
            counter = 0
            api_seen = []
            intercept_errors = []

            async def command(method, params=None):
                nonlocal counter
                counter += 1
                future = asyncio.get_running_loop().create_future()
                pending[counter] = future
                await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                message = await future
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

            async def fulfill(request_id, payload, status=200):
                data = json.dumps(payload, separators=(",", ":")).encode()
                await command(
                    "Fetch.fulfillRequest",
                    {
                        "requestId": request_id,
                        "responseCode": status,
                        "responseHeaders": [{"name": "Content-Type", "value": "application/json; charset=utf-8"}],
                        "body": base64.b64encode(data).decode(),
                    },
                )

            async def intercept(params):
                request = params["request"]
                parsed = urlparse(request["url"])
                method = request.get("method", "GET").upper()
                path = parsed.path
                if "/api/v1" not in path:
                    await command("Fetch.continueRequest", {"requestId": params["requestId"]})
                    return
                raw_body = request.get("postData") or ""
                try:
                    body = json.loads(raw_body) if raw_body and raw_body.lstrip().startswith(("{", "[")) else {}
                except Exception:
                    body = {}
                api_seen.append({"method": method, "path": path})
                FIXTURES.api_requests.append({"method": method, "path": path})
                try:
                    payload, status = FIXTURES.reply(path, method, parse_qs(parsed.query), body)
                    if status == 0:
                        payload = {
                            "detail": {
                                "code": "manual_fixture_missing",
                                "message": f"Sample browser fixture missing for {method} {path}; request blocked.",
                            }
                        }
                        status = 501
                        FIXTURES.unknown.append({"path": path, "method": method})
                    await fulfill(params["requestId"], payload, status)
                except Exception as exc:
                    intercept_errors.append(f"{method} {path}: {type(exc).__name__}: {exc}")
                    await fulfill(
                        params["requestId"],
                        {"detail": {"code": "manual_fixture_error", "message": f"Sample fixture error: {type(exc).__name__}"}},
                        500,
                    )

            async def receive():
                async for raw in ws:
                    message = json.loads(raw)
                    if "id" in message:
                        future = pending.pop(message["id"], None)
                        if future and not future.done():
                            future.set_result(message)
                    elif message.get("method") == "Fetch.requestPaused":
                        asyncio.create_task(intercept(message["params"]))

            reader = asyncio.create_task(receive())

            async def evaluate(expression, await_promise=True):
                result = await command(
                    "Runtime.evaluate",
                    {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": await_promise,
                        "userGesture": True,
                    },
                )
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"])
                return result.get("result", {}).get("value")

            async def wait_for(expression, label, timeout=20):
                for _ in range(timeout * 10):
                    value = await evaluate(expression)
                    if value:
                        return value
                    await asyncio.sleep(0.1)
                body = await evaluate("document.body.innerText")
                raise AssertionError(f"Timed out waiting for {label}; rendered body: {body}")

            async def click_text(text, selector="button"):
                expression = (
                    "(() => {const e=[...document.querySelectorAll("
                    f"{json.dumps(selector)}"
                    ")].find(n=>n.textContent.trim().includes("
                    f"{json.dumps(text)}"
                    ")||n.getAttribute('aria-label')?.includes("
                    f"{json.dumps(text)}"
                    "));if(!e)return false;e.click();return true})()"
                )
                if not await evaluate(expression):
                    raise AssertionError(f"Could not find clickable {selector}: {text}")
                await asyncio.sleep(0.35)

            async def set_value(selector, value):
                expression = (
                    "(() => {const e=document.querySelector("
                    f"{json.dumps(selector)}"
                    ");if(!e)return false;const setter=Object.getOwnPropertyDescriptor("
                    "Object.getPrototypeOf(e),'value')?.set;if(setter)setter.call(e,"
                    f"{json.dumps(value)}"
                    ");else e.value="
                    f"{json.dumps(value)}"
                    ";e.dispatchEvent(new Event('input',{bubbles:true}));"
                    "e.dispatchEvent(new Event('change',{bubbles:true}));return true})()"
                )
                if not await evaluate(expression):
                    raise AssertionError(f"Could not set input {selector}")
                await asyncio.sleep(0.15)

            async def set_labeled_value(label_text, value, scope=None):
                expression = (
                    "(() => {const label=[...document.querySelectorAll('label')].find("
                    f"e=>e.textContent.trim()==={json.dumps(label_text)}"
                    "&&("
                    f"{json.dumps(scope)}===null||!!e.closest({json.dumps(scope)})"
                    "));const e=label?.control||label?.querySelector('input,textarea,select');"
                    "if(!e)return false;const setter=Object.getOwnPropertyDescriptor("
                    "Object.getPrototypeOf(e),'value')?.set;if(setter)setter.call(e,"
                    f"{json.dumps(value)}"
                    ");else e.value="
                    f"{json.dumps(value)}"
                    ";e.dispatchEvent(new Event('input',{bubbles:true}));"
                    "e.dispatchEvent(new Event('change',{bubbles:true}));return true})()"
                )
                if not await evaluate(expression):
                    raise AssertionError(f"Could not set labeled field: {label_text}")
                await asyncio.sleep(0.15)

            async def select_radio(value):
                selector = f'input[type="radio"][value="{value}"]'
                if not await evaluate(
                    "(() => {const e=document.querySelector("
                    f"{json.dumps(selector)}"
                    ");if(!e)return false;e.click();return true})()"
                ):
                    raise AssertionError(f"Radio value not found: {value}")
                await asyncio.sleep(0.15)

            async def check(selector):
                if not await evaluate(
                    "(() => {const e=document.querySelector("
                    f"{json.dumps(selector)}"
                    ");if(!e)return false;if(!e.checked)e.click();return e.checked})()"
                ):
                    raise AssertionError(f"Could not check {selector}")

            async def choose_combobox(button_id, search):
                if not await evaluate(
                    "(() => {const e=document.getElementById("
                    f"{json.dumps(button_id)}"
                    ");if(!e)return false;e.click();return true})()"
                ):
                    raise AssertionError(f"Location control not found: {button_id}")
                await asyncio.sleep(0.2)
                await set_value(f'input[role="combobox"]', search)
                await asyncio.sleep(0.2)
                if not await evaluate(
                    "(() => {const o=[...document.querySelectorAll('[role=option]')].find("
                    f"e=>e.textContent.trim().toLowerCase().includes({json.dumps(search.lower())})"
                    ");if(!o)return false;o.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,button:0}));return true})()"
                ):
                    raise AssertionError(f"No geographic choice contains {search}")
                await asyncio.sleep(0.25)

            async def set_badge(title, caption):
                await evaluate(
                    """(() => {
                      let badge=document.getElementById('manual-sample-badge');
                      if(!badge){badge=document.createElement('div');badge.id='manual-sample-badge';document.body.appendChild(badge);}
                      badge.textContent='SAMPLE DATA — demonstration only';
                      Object.assign(badge.style,{position:'fixed',top:'12px',right:'14px',zIndex:'2147483647',
                        background:'#17372d',color:'#fff',border:'2px solid #f2c879',borderRadius:'7px',
                        padding:'9px 13px',font:'700 14px/1.2 system-ui,sans-serif',letterSpacing:'.01em',
                        boxShadow:'0 3px 14px #0005',pointerEvents:'none'});
                      let callout=document.getElementById('manual-capture-caption');
                      if(!callout){callout=document.createElement('div');callout.id='manual-capture-caption';document.body.appendChild(callout);}
                      callout.innerHTML='';
                      const strong=document.createElement('strong');strong.textContent=TITLE;
                      const span=document.createElement('span');span.textContent=CAPTION;
                      callout.append(strong,span);
                      Object.assign(callout.style,{position:'fixed',right:'14px',bottom:'14px',zIndex:'2147483647',
                        maxWidth:'340px',padding:'12px 15px',display:'grid',gap:'4px',borderRadius:'8px',
                        background:'#fff',color:'#17372d',border:'1px solid #c9d5cb',
                        boxShadow:'0 4px 16px #0003',font:'13px/1.4 system-ui,sans-serif',pointerEvents:'none'});
                      strong.style.fontWeight='800';strong.style.fontSize='14px';
                      return true;
                    })()"""
                    .replace("TITLE", json.dumps(title))
                    .replace("CAPTION", json.dumps(caption))
                )

            async def navigate(path, role="member", height=1040, settle=2.0, unauthenticated=False):
                FIXTURES.role = role
                FIXTURES.unauthenticated = unauthenticated
                await command(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 1440, "height": height, "deviceScaleFactor": 1, "mobile": False},
                )
                await command("Page.navigate", {"url": f"https://{domain}{path}"})
                await wait_for("document.readyState==='complete' && !!document.body", f"page {path}")
                await asyncio.sleep(settle)

            async def screenshot(name, title, caption, scroll=0):
                await evaluate(f"window.scrollTo(0,{int(scroll)})")
                await asyncio.sleep(0.3)
                await set_badge(title, caption)
                await asyncio.sleep(0.2)
                captured = await command(
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": False, "fromSurface": True},
                )
                image = Image.open(BytesIO(base64.b64decode(captured["data"]))).convert("RGB")
                target_path = OUT / f"{ASSET_NAMES.get(name, name)}.webp"
                image.save(target_path, "WEBP", quality=82, method=6)
                print(f"saved {target_path.relative_to(ROOT)} ({image.width}x{image.height})")

            async def click_location_for_member_signup():
                await choose_combobox("signup-location-country", "United States")
                await choose_combobox("signup-location-state", "California")
                await choose_combobox("signup-location-city", "Los Angeles")

            async def fill_member_signup():
                await set_value("#signup-first-name", "Sample")
                await set_value("#signup-last-name", "Rider")
                await set_value("#signup-email", SAMPLE_EMAIL)
                mobile = await evaluate("document.querySelector('[aria-label=\"Mobile number\"]')?.tagName")
                if mobile:
                    await set_value('[aria-label="Mobile number"]', "555 010 0400")
                await click_location_for_member_signup()
                await select_radio("BOTH")
                await set_value("#signup-password", "SampleHorse7")
                await set_value("#signup-password-confirmation", "SampleHorse7")
                await check("#accept-terms")
                await check("#accept-privacy")

            async def capture_provider_insights():
                await navigate("/provider/insights", role="provider", height=2040)
                await wait_for(
                    "document.body.innerText.includes('Sample Meadow Equine Clinic')"
                    "&&document.body.innerText.includes('Activity over time')"
                    "&&document.body.innerText.includes('Current snapshot')",
                    "populated provider insights dashboard",
                )
                await screenshot(
                    "role-provider-insights-overview",
                    "Provider insights · engagement overview",
                    "Synthetic aggregate cards, activity trends, contact breakdown, current profile totals, and source-coverage notes.",
                )

                filtered_from = (TODAY - timedelta(days=6)).isoformat()
                await set_value("#insights-period", "custom")
                await wait_for("!!document.querySelector('#insights-from')&&!!document.querySelector('#insights-to')", "custom insight date controls")
                await set_value("#insights-from", filtered_from)
                await set_value("#insights-to", TODAY.isoformat())
                await click_text("Apply dates")
                expected_views = sum(2 + (offset % 5) for offset in range(7))
                await wait_for(
                    "Array.from(document.querySelectorAll('[aria-label=\"Engagement metrics\"] article'))"
                    f".some(card=>card.textContent.includes({json.dumps(str(expected_views))}))",
                    "custom insights filter result",
                )
                await evaluate(
                    """(() => {
                      const summaries=[...document.querySelectorAll('summary')]
                        .filter(item=>item.textContent.includes('View data table'));
                      if(summaries.length<2)return false;
                      summaries[0].click();summaries[1].click();return true;
                    })()"""
                )
                await wait_for("document.querySelectorAll('table').length===2", "trend data tables")
                await screenshot(
                    "role-provider-insights-filtered",
                    "Provider insights · custom period",
                    "Applying the last-seven-days custom range returns a distinct fixture result with date controls and both trend data tables.",
                )

                requests_before_refresh = FIXTURES.provider_insights_requests
                await click_text("Refresh")
                for _ in range(50):
                    if FIXTURES.provider_insights_requests > requests_before_refresh:
                        break
                    await asyncio.sleep(0.1)
                if FIXTURES.provider_insights_requests <= requests_before_refresh:
                    raise AssertionError("Refresh did not request provider insights from the synthetic fixture.")
                await asyncio.sleep(0.45)
                await screenshot(
                    "role-provider-insights-refreshed",
                    "Provider insights · refreshed",
                    "Refresh retrieves a new synthetic response and advances the displayed update time; no live analytics API is contacted.",
                )

            async def capture_provider_workspace_refresh():
                FIXTURES.provider_profile = copy.deepcopy(PROFILE)
                await navigate("/provider/account", role="provider", height=1120)
                await wait_for(
                    "!!document.querySelector('[aria-label=\"Provider profile sections\"]')"
                    "&&document.body.innerText.includes('Manage your submitted profile')",
                    "provider account navigation",
                )
                await screenshot(
                    "role-provider-signed-in",
                    "Provider portal · signed in",
                    "A signed-in provider opens the profile workspace with Account, Insights, and Messages navigation.",
                )
                await screenshot(
                    "role-provider-account-basic",
                    "Provider workspace · basic details",
                    "Review and maintain the practice's public-facing identity before saving a proposal.",
                )
                await click_text("Professional details", "[role=tab]")
                await screenshot(
                    "role-provider-account-professional",
                    "Provider workspace · professional details",
                    "Professional credentials and qualifications are maintained in their own section.",
                )
                await click_text("Services", "[role=tab]")
                await screenshot(
                    "role-provider-account-services",
                    "Provider workspace · services",
                    "Service availability and working-radius controls are grouped separately from profile basics.",
                )
                await click_text("Contact & location", "[role=tab]")
                await screenshot(
                    "role-provider-account-contacts",
                    "Provider workspace · contacts and locations",
                    "Contact collections and multiple locations expose a single primary selection.",
                    200,
                )
                await click_text("Photos", "[role=tab]")
                await screenshot(
                    "role-provider-account-photos",
                    "Provider workspace · photos",
                    "Existing sample photos support alt text, captions, removal, and the displayed-first selection.",
                )
                await evaluate(
                    """(async()=>{const input=document.querySelector('#provider-panel-photos input[type=file]');
                    if(!input)throw new Error('provider photo file input missing');
                    const response=await fetch('/horse-panel.jpg');const blob=await response.blob();
                    const file=new File([blob],'sample-horse-photo.jpg',{type:'image/jpeg'});
                    const transfer=new DataTransfer();transfer.items.add(file);input.files=transfer.files;
                    input.dispatchEvent(new Event('change',{bubbles:true}));return true})()"""
                )
                await wait_for("document.body.innerText.includes('sample-horse-photo.jpg')", "staged local sample image")
                await set_labeled_value("Alt text", "Sample horse in a peaceful field", '[class*="stagedPhoto"]')
                await set_labeled_value("Image title", "Sample care-setting image", '[class*="stagedPhoto"]')
                await click_text("Upload photo")
                await wait_for("document.body.innerText.includes('Uploaded, not yet saved')", "uploaded-but-unsaved state")
                await screenshot(
                    "role-provider-photo-uploaded",
                    "Provider workspace · uploaded photo",
                    "Photo upload is distinct from saving the profile; the screen clearly shows it is not yet included.",
                )
                await click_text("Save profile")
                await wait_for("document.body.innerText.includes('awaiting review')", "provider pending review outcome")
                await screenshot(
                    "role-provider-update-pending",
                    "Provider workspace · pending review",
                    "Saving published-profile changes creates a review request while the live listing remains unchanged.",
                )
                FIXTURES.provider_profile["profile_update"]["review_status"] = "REJECTED"
                FIXTURES.provider_profile["profile_update"]["rejection_reason"] = "Sample feedback: please clarify the photo caption."
                await navigate("/provider/account", role="provider", height=1120)
                await wait_for("document.body.innerText.includes('declined')", "provider rejected update")
                await screenshot(
                    "role-provider-update-rejected",
                    "Provider workspace · revision requested",
                    "Sample reviewer feedback is displayed with a route to revise and resubmit the unpublished proposal.",
                )
                await click_text("Discard draft and reload approved listing")
                await wait_for("document.body.innerText.includes('draft was discarded')", "provider draft discarded")
                await screenshot(
                    "role-provider-update-discarded",
                    "Provider workspace · draft discarded",
                    "Discarding resets the sample profile to its approved listing and confirms the result.",
                )
                await click_text("Member feedback")
                await wait_for("document.querySelector('[data-testid=\"feedback-drawer\"]')?.hidden===false", "provider member feedback drawer")
                await screenshot(
                    "role-provider-member-feedback",
                    "Provider workspace · member feedback",
                    "The feedback drawer shows published sample member reviews separately from profile editing.",
                )
                await click_text("Close", '[data-testid="feedback-drawer"] button')
                await navigate("/provider/account", role="provider", height=1120)
                await wait_for("!!document.querySelector('[aria-label=\"Provider profile sections\"]')", "provider visits workspace")
                await click_text("Visits", "[role=tab]")
                await screenshot(
                    "role-provider-visits-history",
                    "Provider workspace · recorded visit history",
                    "Recorded trips are grouped as previous, current, and upcoming; the history is read-only.",
                    260,
                )
                await click_text("Add visit")
                await wait_for("!!document.querySelector('#portal-visit-0-start-date')", "proposed provider trip form")
                await screenshot(
                    "role-provider-trip-proposal",
                    "Provider workspace · propose a visit",
                    "Proposed trip details are separate from approved visit history until saved and reviewed.",
                    420,
                )
                await capture_provider_insights()

                FIXTURES.reset_message_conversations()
                await navigate("/provider/messages", role="provider", height=1120)
                await wait_for(
                    "document.body.innerText.includes('Sample Rider')&&document.body.innerText.includes('Choose a conversation')",
                    "provider messages inbox",
                )
                await screenshot(
                    "role-provider-messages-inbox",
                    "Provider messages · inbox",
                    "The provider workspace shows a populated sample member conversation and synthetic unread status.",
                )
                await click_text("Sample Rider", 'a[href="/provider/messages/sample-private-conversation"]')
                await wait_for(
                    "document.body.innerText.includes('Sample provider reply:')&&!!document.querySelector('#private-message-reply')",
                    "provider conversation thread",
                )
                await screenshot(
                    "role-provider-messages-thread",
                    "Provider messages · conversation",
                    "The provider can read the labelled sample exchange and the member contact snapshot supplied by the fixture.",
                )
                await set_value(
                    "#private-message-reply",
                    "Sample provider reply: Thank you. We can discuss suitable visit times through this private thread.",
                )
                await click_text("Send reply")
                await wait_for("document.body.innerText.includes('Sample provider reply: Thank you.')", "provider reply outcome")
                await screenshot(
                    "role-provider-messages-replied",
                    "Provider messages · reply sent",
                    "The sample provider reply appears in the thread; the write is fixture-only and sends no email.",
                )

            await command("Page.enable")
            await command(
                "Fetch.enable",
                {"patterns": [{"urlPattern": "*api/v1*", "requestStage": "Request"}]},
            )
            await command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                      try{Object.defineProperty(navigator,'geolocation',{configurable:true,value:{
                        getCurrentPosition(ok){ok({coords:{latitude:34.05,longitude:-118.25,accuracy:100}})},
                        watchPosition(ok){ok({coords:{latitude:34.05,longitude:-118.25,accuracy:100}});return 1},
                        clearWatch(){}
                      }})}catch(e){}
                    """
                },
            )
            await command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                      window.confirm=()=>true;
                      window.alert=()=>{};
                    """
                },
            )

            if provider_refresh:
                await capture_provider_workspace_refresh()
                current_body = await evaluate("document.body.innerText")
                if "SAMPLE DATA — demonstration only" not in current_body:
                    raise AssertionError("The visible synthetic-data badge is missing from the final rendered screen.")
                if intercept_errors:
                    raise AssertionError("Fixture interception errors: " + " | ".join(intercept_errors))
                if FIXTURES.unknown:
                    summary = ", ".join(f"{item['method']} {item['path']}" for item in FIXTURES.unknown)
                    raise AssertionError(f"Unmatched API routes were blocked by fixtures and must be modeled: {summary}")
                print(f"Intercepted {len(api_seen)} /api/v1 requests; no unknown API routes reached the backend.")
                print("Refreshed signed-in provider navigation, provider workspace, insights, and messaging captures only.")
                reader.cancel()
                return

            # Public member signup -> email verification -> member sign-in.
            await navigate("/signup", role="member")
            await wait_for("!!document.querySelector('#signup-email')", "member registration form")
            await screenshot(
                "role-member-registration",
                "Member account · registration form",
                "The public signup form collects contact details, role, and password before email verification.",
            )
            await fill_member_signup()
            await click_text("Create account")
            await wait_for("document.body.innerText.includes('Check your inbox')", "member verification handoff")
            await screenshot(
                "role-member-verification-handoff",
                "Member account · verification handoff",
                "A successful sample registration shows the verification state; no email is sent.",
            )
            await navigate("/verify-email?token=sample-member-verification", role="member", settle=0.1)
            await wait_for("document.body.innerText.includes('Email verified successfully')", "member verified state")
            await screenshot(
                "role-member-verification-complete",
                "Member account · verified",
                "The sample verification link resolves to the member sign-in route without exposing its token.",
            )
            await navigate("/providers", role="member", unauthenticated=True)
            await wait_for("!!document.querySelector('#member-email')", "member sign-in")
            await screenshot(
                "role-member-sign-in",
                "Member account · sign in",
                "Verified members use the dedicated member sign-in page.",
            )
            await set_value("#member-email", SAMPLE_EMAIL)
            await set_value("#member-password", "SampleHorse7")
            await click_text("Sign in")
            await wait_for("document.body.innerText.includes('Sample Meadow Equine Clinic')", "member signed-in directory")
            await screenshot(
                "role-member-signed-in",
                "Member account · signed in",
                "A successful sample sign-in opens the protected member directory.",
            )

            # Provider signup and secure verification/password lifecycle.
            await navigate("/provider/signup", role="member")
            await wait_for("!!document.querySelector('#provider-email')", "provider signup form")
            await screenshot(
                "role-provider-registration",
                "Provider application · registration",
                "Provider applicants select a practice type, credentials, specialties, and service location.",
                0,
            )
            await set_value("#provider-signup-name", "Sample Meadow Equine Clinic")
            await select_radio("CLINIC")
            await set_value("#provider-first-name", "Sample")
            await set_value("#provider-last-name", "Applicant")
            await set_value("#provider-email", PROVIDER_EMAIL)
            await set_value('[aria-label="Mobile number"]', "555 010 0800")
            await set_value("#provider-professional-title", "Sample Equine Veterinarian")
            await set_value("#provider-years-experience", "8")
            await set_value("#provider-postal-code", "123")
            await choose_combobox("provider-signup-location-country", "United States")
            await choose_combobox("provider-signup-location-state", "California")
            await choose_combobox("provider-signup-location-city", "Los Angeles")
            await set_value("#provider-working-address", "300 Sample Orchard Way")
            await set_value("#provider-password", "SampleHorse7")
            await set_value("#provider-password-confirmation", "SampleHorse7")
            # Select available specialization and language using the actual widgets.
            await click_text("Select specializations", "button")
            await click_text("Equine internal medicine", "[role=option],button")
            await click_text("Select languages", "button")
            await click_text("English", "[role=option],button")
            await check("#provider-accept-terms")
            await check("#provider-accept-privacy")
            await click_text("Submit provider application")
            await wait_for("document.body.innerText.includes('Check your inbox')", "provider email verification handoff")
            await screenshot(
                "role-provider-verification-handoff",
                "Provider application · verification handoff",
                "Submitting a sample application displays the verification handoff; delivery remains a browser fixture.",
            )
            await navigate("/verify-email?token=sample-provider-verification", role="member", settle=0.1)
            await wait_for("document.body.innerText.includes('Email verified successfully')", "provider verification")
            await screenshot(
                "role-provider-verification-complete",
                "Provider application · verified",
                "Provider email verification confirms the next sign-in step without exposing the synthetic token.",
            )
            await navigate("/provider/setup-password?token=sample-setup-only", role="member")
            await wait_for("!!document.querySelector('#portal-password')", "provider password setup")
            await set_value("#portal-password", "SampleHorse7")
            await set_value("#portal-password-confirmation", "SampleHorse7")
            await screenshot(
                "role-provider-password-setup",
                "Provider portal · set password",
                "An invited or approved provider sets a secure portal password using a one-time synthetic link.",
            )
            await click_text("Set password")
            await wait_for("document.body.innerText.includes('Password set')", "provider password setup completion")
            await screenshot(
                "role-provider-password-ready",
                "Provider portal · password ready",
                "The success state directs the provider to portal sign-in; the fixture does not create credentials.",
            )
            await navigate("/provider/reset-password?token=sample-recovery-only", role="member")
            await wait_for("!!document.querySelector('#portal-password')", "provider password recovery")
            await set_value("#portal-password", "SampleHorse8")
            await set_value("#portal-password-confirmation", "SampleHorse8")
            await screenshot(
                "role-provider-password-recovery",
                "Provider portal · password recovery",
                "Providers can replace a forgotten password from a separate recovery link.",
            )
            await click_text("Reset password")
            await wait_for("document.body.innerText.includes('Password reset')", "provider password recovery completion")
            await screenshot(
                "role-provider-password-recovered",
                "Provider portal · recovery complete",
                "The sample reset flow returns a clear completion state and sign-in route.",
            )
            await navigate("/provider/account", role="guest", unauthenticated=True)
            await wait_for("!!document.querySelector('#provider-login-email')", "provider authentication guard")
            await screenshot(
                "role-provider-access-guard",
                "Provider portal · access guard",
                "Unauthenticated requests for the provider workspace are returned to provider sign-in.",
            )
            await navigate("/provider/login", role="provider", unauthenticated=True)
            await wait_for("!!document.querySelector('#provider-login-email')", "provider sign-in")
            await screenshot(
                "role-provider-signin-form",
                "Provider portal · sign in",
                "Approved providers use the separate provider portal sign-in route.",
            )
            await set_value("#provider-login-email", PROVIDER_EMAIL)
            await set_value("#provider-login-password", "SampleHorse7")
            await click_text("Sign in to provider portal")
            await wait_for("document.body.innerText.includes('Manage your submitted profile')", "provider signed-in workspace")
            await screenshot(
                "role-provider-signed-in",
                "Provider portal · signed in",
                "A successful sample sign-in opens the provider profile workspace.",
            )

            # Invitation completion: actual save-draft and final-submit controls.
            await navigate(f"/provider/invite/{SAMPLE_TOKEN}", role="member", height=1040)
            await wait_for("document.body.innerText.includes('Complete your clinic profile')", "invitation profile form")
            await screenshot(
                "role-invitation-profile",
                "Provider invitation · complete profile",
                "The invited applicant can review the prefilled Sample profile before saving a draft or submitting.",
            )
            await click_text("Save draft")
            await wait_for("document.body.innerText.includes('Draft saved')", "invitation draft save")
            await screenshot(
                "role-invitation-draft-saved",
                "Provider invitation · draft saved",
                "Save draft returns a visible confirmation and leaves the sample invitation resumable.",
            )
            await set_value("#invitation-password", "SampleHorse7")
            await set_value("#invitation-password-confirmation", "SampleHorse7")
            await click_text("Submit for review")
            await wait_for("window.location.pathname==='/provider/invite/success'", "invitation final submission")
            await screenshot(
                "role-invitation-submitted",
                "Provider invitation · submitted",
                "Final submission reaches the shipped confirmation screen using only a sample invitation fixture.",
            )

            # Provider workspace collections and proposal outcomes.
            FIXTURES.role = "provider"
            FIXTURES.provider_profile = copy.deepcopy(PROFILE)
            await navigate("/provider/account", role="provider", height=1120)
            await wait_for("!!document.querySelector('[aria-label=\"Provider profile sections\"]')", "provider account")
            await screenshot(
                "role-provider-account-basic",
                "Provider workspace · basic details",
                "Review and maintain the practice's public-facing identity before saving a proposal.",
            )
            await click_text("Professional details", "[role=tab]")
            await screenshot(
                "role-provider-account-professional",
                "Provider workspace · professional details",
                "Professional credentials and qualifications are maintained in their own section.",
            )
            await click_text("Services", "[role=tab]")
            await screenshot(
                "role-provider-account-services",
                "Provider workspace · services",
                "Service availability and working-radius controls are grouped separately from profile basics.",
            )
            await click_text("Contact & location", "[role=tab]")
            await screenshot(
                "role-provider-account-contacts",
                "Provider workspace · contacts and locations",
                "Contact collections and multiple locations expose a single primary selection.",
                200,
            )
            await click_text("Photos", "[role=tab]")
            await screenshot(
                "role-provider-account-photos",
                "Provider workspace · photos",
                "Existing sample photos support alt text, captions, removal, and the displayed-first selection.",
            )
            # Use the shipped horse photo as a local sample image; no patient or location image is uploaded.
            await evaluate(
                """(async()=>{const input=document.querySelector('#provider-panel-photos input[type=file]');
                if(!input)throw new Error('provider photo file input missing');
                const response=await fetch('/horse-panel.jpg');const blob=await response.blob();
                const file=new File([blob],'sample-horse-photo.jpg',{type:'image/jpeg'});
                const transfer=new DataTransfer();transfer.items.add(file);input.files=transfer.files;
                input.dispatchEvent(new Event('change',{bubbles:true}));return true})()"""
            )
            await wait_for("document.body.innerText.includes('sample-horse-photo.jpg')", "staged local sample image")
            await set_labeled_value("Alt text", "Sample horse in a peaceful field", '[class*="stagedPhoto"]')
            await set_labeled_value("Image title", "Sample care-setting image", '[class*="stagedPhoto"]')
            await click_text("Upload photo")
            await wait_for("document.body.innerText.includes('Uploaded, not yet saved')", "uploaded-but-unsaved state")
            await screenshot(
                "role-provider-photo-uploaded",
                "Provider workspace · uploaded photo",
                "Photo upload is distinct from saving the profile; the screen clearly shows it is not yet included.",
            )
            await click_text("Save profile")
            await wait_for("document.body.innerText.includes('awaiting review')", "provider pending review outcome")
            await screenshot(
                "role-provider-update-pending",
                "Provider workspace · pending review",
                "Saving published-profile changes creates a review request while the live listing remains unchanged.",
            )
            # Rejected and discarded states use explicit synthetic fixture status transitions.
            FIXTURES.provider_profile["profile_update"]["review_status"] = "REJECTED"
            FIXTURES.provider_profile["profile_update"]["rejection_reason"] = "Sample feedback: please clarify the photo caption."
            await navigate("/provider/account", role="provider", height=1120)
            await wait_for("document.body.innerText.includes('declined')", "provider rejected update")
            await screenshot(
                "role-provider-update-rejected",
                "Provider workspace · revision requested",
                "Sample reviewer feedback is displayed with a route to revise and resubmit the unpublished proposal.",
            )
            await click_text("Discard draft and reload approved listing")
            await wait_for("document.body.innerText.includes('draft was discarded')", "provider draft discarded")
            await screenshot(
                "role-provider-update-discarded",
                "Provider workspace · draft discarded",
                "Discarding resets the sample profile to its approved listing and confirms the result.",
            )
            await click_text("Member feedback")
            await wait_for("document.querySelector('[data-testid=\"feedback-drawer\"]')?.hidden===false", "provider member feedback drawer")
            await screenshot(
                "role-provider-member-feedback",
                "Provider workspace · member feedback",
                "The feedback drawer shows published sample member reviews separately from profile editing.",
            )
            await click_text("Close", '[data-testid="feedback-drawer"] button')
            await navigate("/provider/account", role="provider", height=1120)
            await wait_for("!!document.querySelector('[aria-label=\"Provider profile sections\"]')", "provider visits workspace")
            await click_text("Visits", "[role=tab]")
            await screenshot(
                "role-provider-visits-history",
                "Provider workspace · recorded visit history",
                "Recorded trips are grouped as previous, current, and upcoming; the history is read-only.",
                260,
            )
            await click_text("Add visit")
            await wait_for("!!document.querySelector('#portal-visit-0-start-date')", "proposed provider trip form")
            await screenshot(
                "role-provider-trip-proposal",
                "Provider workspace · propose a visit",
                "Proposed trip details are separate from approved visit history until saved and reviewed.",
                420,
            )
            await capture_provider_insights()

            # Member provider discovery: filters, opt-in location, saved list.
            await navigate("/providers", role="member", height=1120)
            await wait_for("document.body.innerText.includes('Sample Meadow Equine Clinic')", "provider directory")
            await screenshot(
                "role-member-directory",
                "Member directory · provider results",
                "Directory cards summarize sample expertise, locality, ratings, contact options, and saved status.",
            )
            await click_text("More filters")
            await wait_for("!!document.querySelector('#more-filters')", "directory advanced filters")
            await screenshot(
                "role-member-directory-filters",
                "Member directory · refine results",
                "Optional provider, rating, emergency, and location controls are expanded only when requested.",
                0,
            )
            await click_text("Sort closest first")
            await wait_for("document.body.innerText.includes('4.2 km from your location')", "synthetic location-filtered results")
            await screenshot(
                "role-member-directory-location",
                "Member directory · location controls",
                "Distance results use the browser's synthetic sample location only after the member opts in.",
            )
            await click_text("Save for later")
            await wait_for("document.body.innerText.includes('Saved ✓')", "saved provider toggle")
            await screenshot(
                "role-member-directory-saved",
                "Member directory · save a provider",
                "Saving a sample provider updates the saved state without creating a live account or record.",
            )
            await navigate("/providers?saved=true", role="member", height=1120)
            await wait_for(
                "document.body.innerText.includes('Saved providers')&&document.body.innerText.includes('Sample Meadow Equine Clinic')",
                "saved providers list",
            )
            await screenshot(
                "role-member-saved-providers",
                "Member directory · saved providers",
                "A saved listing is available again from the member-only Saved providers view.",
            )

            # Member provider detail: photos, contact, locations, visit and review.
            await navigate("/providers/sample-clinic-id", role="member", height=1120)
            await wait_for("document.body.innerText.includes('Sample Meadow Equine Clinic')", "member provider detail")
            await wait_for("document.body.innerText.includes('Message provider')", "provider message availability")
            await screenshot(
                "role-member-provider-detail",
                "Provider profile · overview",
                "The sample provider profile includes a live-availability-gated Message provider control alongside direct contact.",
            )
            await click_text("View photos")
            await wait_for("!!document.querySelector('[aria-label=\"Provider photo gallery\"]')", "photo gallery")
            await screenshot(
                "role-member-provider-gallery",
                "Provider profile · photo gallery",
                "The gallery opens the actual shipped profile photos with alt text, captions, and a close control.",
            )
            await click_text("Close photo gallery")
            await evaluate("document.getElementById('locations')?.scrollIntoView({block:'start'})")
            await screenshot(
                "role-member-provider-locations",
                "Provider profile · locations and visits",
                "Multiple sample locations and scheduled visiting periods are informational, not appointment slots.",
            )
            await evaluate("document.getElementById('write-review')?.scrollIntoView({block:'start'})")
            await wait_for("!!document.querySelector('#review-comment')", "provider review form")
            await screenshot(
                "role-member-review-form",
                "Provider profile · add a review",
                "Members can select a rating and write their experience; new text is held for moderation.",
            )
            await set_value("#review-comment", "Sample review: thoughtful care and clear next steps.")
            await click_text("Submit review")
            await wait_for("document.body.innerText.includes('awaiting publication')", "review moderation outcome")
            await screenshot(
                "role-member-review-pending",
                "Provider profile · review pending",
                "After submission the sample review is marked pending; only published text is shown publicly.",
                1900,
            )

            # Visiting-provider calendar and detail schedule use a current-month fixture.
            await navigate("/providers/visiting-calendar", role="member", height=1100)
            await wait_for("document.body.innerText.includes('Find visiting care, day by day')", "visiting-provider calendar")
            await evaluate(
                "(() => {const d=new Date();d.setDate(d.getDate()+8);"
                "const b=[...document.querySelectorAll('button[aria-label]')].find(e=>e.getAttribute('aria-label').includes('1 visiting provider'));"
                "b?.click();return !!b})()"
            )
            await wait_for("document.body.innerText.includes('Sample Visiting Veterinarian')", "selected visit day agenda")
            await screenshot(
                "role-member-visiting-calendar",
                "Visiting care · calendar",
                "The member calendar highlights sample visiting periods and links to provider details.",
            )

            # Member profile collections: stable, horse history, completion and private records.
            await navigate("/profile", role="member", height=1100)
            await wait_for("document.body.innerText.includes('Your profile')", "member account profile")
            await screenshot(
                "role-member-profile",
                "Member account · profile readiness",
                "Profile completion summarizes personal contact details, stable information, and horse records.",
            )
            await evaluate("document.getElementById('stable-profile-section')?.scrollIntoView({block:'start'})")
            await screenshot(
                "role-member-stable-profile",
                "Member account · stable manager",
                "Stable identity, location, and contact fields are available only to the stable-manager role.",
            )
            await evaluate("document.getElementById('horses-profile-section')?.scrollIntoView({block:'start'})")
            await screenshot(
                "role-member-horse-history",
                "Member account · horse history",
                "The horse collection supports individual horse records and the shipped sample image without private data.",
            )
            await navigate("/history", role="member", height=1000)
            await wait_for("document.body.innerText.includes('Browsing history')", "member browsing history")
            await screenshot(
                "role-member-private-history",
                "Member account · private activity",
                "Browsing history is private to the signed-in sample member and can be reopened from the list.",
            )

            await navigate("/my-reviews", role="member", height=1100)
            await wait_for("document.body.innerText.includes('My Reviews & Feedback')", "member review and feedback management")
            await screenshot(
                "role-member-review-moderation",
                "Member account · review moderation",
                "Rejected review feedback remains visible to the member with edit and delete controls.",
            )
            await click_text("Edit review")
            await wait_for("document.body.innerText.includes('Save review')", "member review editor")
            await screenshot(
                "role-member-review-edit",
                "Member account · edit a review",
                "Editing the rejected sample review shows the moderation reminder before resubmission.",
            )
            await set_value("textarea", "Sample revised review: clear communication and helpful care.")
            await click_text("Save review")
            await wait_for("document.body.innerText.includes('awaiting moderation')", "review edit moderation")
            await screenshot(
                "role-member-review-resubmitted",
                "Member account · review resubmitted",
                "Saving a revision returns the review to pending moderation.",
            )
            await click_text("System feedback")
            await wait_for("document.body.innerText.includes('Sample search feedback')", "private member feedback")
            await screenshot(
                "role-member-private-feedback",
                "Member account · private feedback",
                "Private product feedback is separate from provider reviews and not visible to providers.",
            )
            await click_text("Feedback on EquiConnected")
            await wait_for("!!document.querySelector('[role=dialog]')", "feedback message composer")
            await screenshot(
                "role-member-feedback-compose",
                "Member account · send private feedback",
                "The shipped feedback composer makes private-to-team visibility explicit before submission.",
            )
            await set_value("#feedback-category", "Search & Matching")
            await set_value("#feedback-message", "Sample private note: the directory filters were clear.")
            await click_text("Send feedback")
            await wait_for("document.body.innerText.includes('Thank you for helping us improve.')", "private feedback submission")
            await screenshot(
                "role-member-feedback-submitted",
                "Member account · feedback submitted",
                "A private-to-team confirmation follows the sample feedback write; no message or email is sent.",
            )

            # Private messaging: every endpoint below is answered only by synthetic fixtures.
            await navigate("/member/messages", role="member", height=1120)
            await wait_for(
                "document.body.innerText.includes('Sample Meadow Equine Clinic')&&document.body.innerText.includes('Choose a conversation')",
                "member messages inbox",
            )
            await screenshot(
                "role-member-messages-inbox",
                "Member messages · inbox",
                "A sample provider conversation appears in the member inbox with a synthetic unread indicator.",
            )
            await click_text("Sample Meadow Equine Clinic", 'a[href="/member/messages/sample-private-conversation"]')
            await wait_for(
                "document.body.innerText.includes('Sample provider reply:')&&!!document.querySelector('#private-message-reply')",
                "member conversation thread",
            )
            await screenshot(
                "role-member-messages-thread",
                "Member messages · conversation",
                "The populated sample thread shows labelled member and provider messages with a reply composer.",
            )
            await set_value(
                "#private-message-reply",
                "Sample member reply: Thank you. Could you share a few visit times that may work?",
            )
            await click_text("Send reply")
            await wait_for(
                "document.body.innerText.includes('Sample member reply: Thank you.')",
                "member reply outcome",
            )
            await screenshot(
                "role-member-messages-replied",
                "Member messages · reply sent",
                "A sample member reply appears in the thread; the API write is intercepted and no email is sent.",
            )

            # Start from the real profile CTA so the new route and contact-sharing consent are visible.
            await navigate("/providers/sample-clinic-id", role="member", height=1120)
            await wait_for("document.body.innerText.includes('Message provider')", "member provider message control")
            await click_text("Message provider", "a")
            await wait_for(
                "!!document.querySelector('#first-private-message')&&document.body.innerText.includes('Sample Rider')",
                "member start-conversation form",
            )
            await screenshot(
                "role-member-messages-start",
                "Member messages · start a conversation",
                "The sample start form previews synthetic account contact, displays sharing consent, and explains the private channel.",
            )
            await set_value(
                "#first-private-message",
                "Sample member message: Hello, could you share what routine visit options may be available next week?",
            )
            await check('input[type="checkbox"]')
            await click_text("Send private message")
            await wait_for(
                "window.location.pathname.startsWith('/member/messages/sample-started-conversation-')"
                "&&document.body.innerText.includes('Sample member message: Hello,')",
                "member start-conversation outcome",
            )
            await screenshot(
                "role-member-messages-started",
                "Member messages · first message sent",
                "The new sample conversation contains only its labelled synthetic starter message; no real provider or SMTP is contacted.",
            )

            # Reset the fixture dataset so the provider sees one clearly labelled seed thread.
            FIXTURES.reset_message_conversations()
            await navigate("/provider/messages", role="provider", height=1120)
            await wait_for(
                "document.body.innerText.includes('Sample Rider')&&document.body.innerText.includes('Choose a conversation')",
                "provider messages inbox",
            )
            await screenshot(
                "role-provider-messages-inbox",
                "Provider messages · inbox",
                "The provider workspace shows a populated sample member conversation and synthetic unread status.",
            )
            await click_text("Sample Rider", 'a[href="/provider/messages/sample-private-conversation"]')
            await wait_for(
                "document.body.innerText.includes('Sample provider reply:')&&!!document.querySelector('#private-message-reply')",
                "provider conversation thread",
            )
            await screenshot(
                "role-provider-messages-thread",
                "Provider messages · conversation",
                "The provider can read the labelled sample exchange and the member contact snapshot supplied by the fixture.",
            )
            await set_value(
                "#private-message-reply",
                "Sample provider reply: Thank you. We can discuss suitable visit times through this private thread.",
            )
            await click_text("Send reply")
            await wait_for(
                "document.body.innerText.includes('Sample provider reply: Thank you.')",
                "provider reply outcome",
            )
            await screenshot(
                "role-provider-messages-replied",
                "Provider messages · reply sent",
                "The sample provider reply appears in the thread; the write is fixture-only and sends no email.",
            )

            # Verify the complete capture remained synthetic and fail closed.
            current_body = await evaluate("document.body.innerText")
            if "SAMPLE DATA — demonstration only" not in current_body:
                raise AssertionError("The visible synthetic-data badge is missing from the final rendered screen.")
            if intercept_errors:
                raise AssertionError("Fixture interception errors: " + " | ".join(intercept_errors))
            if FIXTURES.unknown:
                summary = ", ".join(f"{item['method']} {item['path']}" for item in FIXTURES.unknown)
                raise AssertionError(f"Unmatched API routes were blocked by fixtures and must be modeled: {summary}")
            print(f"Intercepted {len(api_seen)} /api/v1 requests; no unknown API routes reached the backend.")
            print(
                f"Captured {sum((OUT / f'{name}.webp').exists() for name in ASSET_NAMES.values())} role screenshots "
                f"in {OUT.relative_to(ROOT)}."
            )
            reader.cancel()
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
            chrome.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main(provider_refresh="--provider-refresh" in sys.argv[1:]))