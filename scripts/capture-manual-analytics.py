#!/usr/bin/env python3
"""Capture real admin dashboard/analytics UI using isolated synthetic API fixtures.

The script owns a dedicated Chromium process, profile, and CDP port (9243). Every
request under /api/v1 is fulfilled here; unknown routes fail closed with an
explicit fixture error. No application API request reaches the running server.
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import websockets


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "frontend/public/manual"
CDP_PORT = 9243
CDP_URL = f"http://127.0.0.1:{CDP_PORT}/json"
CHROMIUM = "/repl/tools/bin/chromium"
TIMEZONE = "America/Toronto"
DEMO_TODAY = date(2026, 4, 30)


def metric(key, label, value, unit, basis="period", definition=None, comparison=None):
    result = {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "basis": basis,
        "available": True,
        "partial_coverage": False,
        "definition": definition or f"Sample aggregate for {label.lower()}.",
    }
    if comparison is not None:
        result["comparison"] = {
            "available": True,
            "previous_value": comparison[0],
            "change_percent": comparison[1],
        }
    return result


def period_for(query):
    preset = query.get("preset", ["last_30_days"])[0]
    group_by = query.get("group_by", ["daily"])[0]
    default_periods = {
        "today": (DEMO_TODAY, DEMO_TODAY),
        "yesterday": (DEMO_TODAY - timedelta(days=1), DEMO_TODAY - timedelta(days=1)),
        "last_7_days": (DEMO_TODAY - timedelta(days=6), DEMO_TODAY),
        "last_30_days": (DEMO_TODAY - timedelta(days=29), DEMO_TODAY),
        "this_month": (date(2026, 4, 1), DEMO_TODAY),
        "last_month": (date(2026, 3, 1), date(2026, 3, 31)),
        "all": (date(2026, 1, 1), DEMO_TODAY),
    }
    if preset == "custom":
        start = query.get("date_from", ["2026-04-10"])[0]
        end = query.get("date_to", ["2026-04-23"])[0]
    else:
        start, end = default_periods.get(preset, default_periods["last_30_days"])
        start, end = start.isoformat(), end.isoformat()
    return {
        "preset": preset,
        "date_from": start,
        "date_to": end,
        "group_by": group_by,
    }


def summary(query):
    period = period_for(query)
    sections = {
        "traffic": {
            "coverage": {"available": True, "from": "2026-01-01", "through": "2026-04-30"},
            "metrics": [
                metric(
                    "website_page_views",
                    "Website page views",
                    1837,
                    "views",
                    definition="Eligible public page views in the selected inclusive date range.",
                    comparison=(1600, 14.8),
                ),
                metric(
                    "estimated_visitor_days",
                    "Estimated visitor-days",
                    406,
                    "visitor-days",
                    definition="Browser-deduplicated daily estimates; not verified people.",
                ),
                metric(
                    "directory_views",
                    "Directory views",
                    612,
                    "views",
                    definition="Successful public directory views in the selected period.",
                    comparison=(574, 6.6),
                ),
                metric(
                    "provider_profile_views",
                    "Provider profile views",
                    239,
                    "views",
                    definition="Successful public provider profile views in the selected period.",
                    comparison=(208, 14.9),
                ),
                metric(
                    "legacy_homepage_visits",
                    "Legacy homepage visits",
                    94,
                    "visits",
                    definition="Legacy homepage traffic is reported separately from page views.",
                ),
            ],
        },
        "registrations": {
            "coverage": {"available": True, "from": "2026-01-01", "through": "2026-04-30"},
            "metrics": [
                metric(
                    "public_member_registrations",
                    "New member registrations",
                    42,
                    "accounts",
                    definition="Public member accounts first created during this period.",
                    comparison=(36, 16.7),
                ),
                metric(
                    "verified_registrations",
                    "Verified in selected cohort",
                    34,
                    "accounts",
                    basis="current",
                    definition="Current verification state of accounts registered in this period.",
                ),
            ],
        },
        "providers": {
            "inventory": {
                "total": 87,
                "active": 61,
                "active_published": 55,
                "status": {"ACTIVE": 61, "UNDER_REVIEW": 8, "INACTIVE": 13, "DRAFT": 5},
                "type": {"CLINIC": 39, "DOCTOR": 34, "HOSPITAL": 14},
                "publication": {"PUBLISHED": 55, "UNPUBLISHED": 32},
            },
            "metrics": [
                metric(
                    "provider_applications",
                    "New provider applications",
                    8,
                    "applications",
                    definition="Provider applications submitted in the selected date range.",
                    comparison=(6, 33.3),
                ),
                metric(
                    "provider_application_decisions",
                    "Recorded application decisions",
                    6,
                    "decisions",
                    definition="Application decisions recorded in the selected period.",
                ),
                metric(
                    "application_approvals",
                    "Recorded approvals",
                    4,
                    "decisions",
                ),
                metric(
                    "application_rejections",
                    "Recorded rejections",
                    2,
                    "decisions",
                ),
                metric(
                    "provider_invitations_created",
                    "Invitations created",
                    13,
                    "invitations",
                    definition="Provider invitations created during the selected period.",
                    comparison=(10, 30.0),
                ),
                metric(
                    "provider_invitations_sent",
                    "Invitations sent",
                    11,
                    "invitations",
                ),
            ],
        },
        "applications": {
            "metrics": [
                metric("provider_applications", "New provider applications", 8, "applications"),
                metric("provider_application_decisions", "Recorded application decisions", 6, "decisions"),
            ],
        },
        "invitations": {
            "metrics": [
                metric("provider_invitations_created", "Invitations created", 13, "invitations"),
                metric("provider_invitations_sent", "Invitations sent", 11, "invitations"),
            ],
        },
        "reviews": {
            "coverage": {"available": True, "from": "2026-01-01", "through": "2026-04-30"},
            "metrics": [
                metric(
                    "provider_review_submissions",
                    "Review submissions",
                    12,
                    "reviews",
                    definition="Initial provider-review submissions created during the selected period.",
                    comparison=(9, 33.3),
                ),
                metric(
                    "eligible_review_rating_average",
                    "Current eligible average rating",
                    4.6,
                    "stars",
                    basis="current",
                    definition="Average of published or hidden approved provider ratings.",
                ),
                metric(
                    "eligible_review_rating_count",
                    "Current eligible rating count",
                    11,
                    "ratings",
                    basis="current",
                ),
            ],
        },
        "feedback": {
            "metrics": [
                metric(
                    "platform_feedback_submissions",
                    "Private feedback submissions",
                    5,
                    "feedback",
                    definition="Private feedback records submitted during the selected period.",
                ),
                metric(
                    "feedback_rating_average",
                    "Average platform feedback rating",
                    4.3,
                    "stars",
                    basis="current",
                    definition="Mean of optional ratings received with private feedback.",
                ),
                metric(
                    "feedback_rated_response_count",
                    "Rated feedback responses",
                    7,
                    "responses",
                    basis="current",
                ),
            ],
        },
        "engagement": {
            "metrics": [
                metric(
                    "contact_enquiries",
                    "Accepted enquiries",
                    9,
                    "enquiries",
                    definition="Durably accepted enquiry records in the selected period.",
                    comparison=(7, 28.6),
                ),
                metric(
                    "new_subscribers",
                    "New unique subscribers",
                    3,
                    "subscribers",
                    definition="Unique stored subscriptions received during the selected period.",
                    comparison=(2, 50.0),
                ),
            ],
        },
    }
    return {
        "timezone": TIMEZONE,
        "period": period,
        "tracking_started_date": "2026-01-01",
        "coverage": {
            "traffic_page_views": {
                "available": True,
                "from": "2026-01-01",
                "through": "2026-04-30",
                "partial": False,
            },
            "member_registrations": {
                "available": True,
                "from": "2026-01-01",
                "through": "2026-04-30",
            },
            "provider_reviews": {
                "available": True,
                "from": "2026-01-01",
                "through": "2026-04-30",
            },
        },
        "refreshed_at": "2026-04-30T15:00:00Z",
        "sections": sections,
    }


def series(metric_name, query):
    period = period_for(query)
    start = date.fromisoformat(period["date_from"])
    end = date.fromisoformat(period["date_to"])
    group_by = period["group_by"]
    base = {
        "website_page_views": 61,
        "estimated_visitor_days": 14,
        "directory_views": 22,
        "provider_profile_views": 9,
        "legacy_homepage_visits": 4,
        "public_member_registrations": 2,
        "provider_applications": 1,
        "provider_application_decisions": 1,
        "provider_invitations_created": 2,
        "provider_invitations_sent": 1,
        "provider_review_submissions": 1,
        "platform_feedback_submissions": 1,
        "contact_enquiries": 1,
        "new_subscribers": 1,
    }.get(metric_name, 8)
    if group_by == "weekly":
        buckets = ["2026-W14", "2026-W15", "2026-W16", "2026-W17", "2026-W18"]
    elif group_by == "monthly":
        buckets = ["2026-01", "2026-02", "2026-03", "2026-04"]
    else:
        span = max((end - start).days, 0)
        if span > 45:
            dates = [start + timedelta(days=round(span * index / 13)) for index in range(14)]
        else:
            dates = [start + timedelta(days=index) for index in range(span + 1)]
        buckets = [item.isoformat() for item in dates]
    data = [
        {"bucket": bucket, "value": base + ((index * 13 + len(metric_name)) % 34) - 9}
        for index, bucket in enumerate(buckets)
    ]
    return {
        "metric": metric_name,
        "unit": "views" if "view" in metric_name or "page" in metric_name else "records",
        "timezone": TIMEZONE,
        "period": period,
        "coverage": {"available": True, "from": period["date_from"], "through": period["date_to"]},
        "available": True,
        "partial_coverage": False,
        "data": data,
    }


def breakdown(domain, query):
    period = period_for(query)
    common = {
        "domain": domain,
        "timezone": TIMEZONE,
        "period": period,
        "coverage": {"available": True, "from": period["date_from"], "through": period["date_to"]},
        "definitions": {},
    }
    examples = {
        "traffic": {
            "page_categories": [
                {"label": "Directory", "value": 612},
                {"label": "Provider profiles", "value": 239},
                {"label": "Homepage", "value": 196},
                {"label": "Care guides", "value": 141},
            ],
            "visitor_days": 406,
            "legacy_homepage_visits": 94,
            "coverage_note": {"tracked_since": "2026-01-01"},
        },
        "registrations": {
            "selected_cohort": {
                "roles": {"Horse owner": 27, "Stable manager": 9, "Both roles": 6},
                "verification": {"Verified": 34, "Unverified": 8},
                "account_state": {"Active": 39, "Inactive": 3},
            },
            "role_assignments": {"Horse owner": 33, "Stable manager": 15},
            "account_state": {"Active": 39, "Inactive": 3},
        },
        "providers": {
            "current_inventory": {
                "status": {"ACTIVE": 61, "UNDER_REVIEW": 8, "INACTIVE": 13, "DRAFT": 5},
                "type": {"CLINIC": 39, "DOCTOR": 34, "HOSPITAL": 14},
                "publication": {"PUBLISHED": 55, "UNPUBLISHED": 32},
            },
            "total": 87,
        },
        "applications": {
            "submitted_cohort_current_status": {
                "PENDING_REVIEW": 3,
                "APPROVED": 4,
                "REJECTED": 1,
            },
            "all_current_status": {
                "PENDING_REVIEW": 7,
                "APPROVED": 28,
                "REJECTED": 6,
                "AWAITING_EMAIL_VERIFICATION": 2,
            },
            "period_decisions": {"Approved": 4, "Rejected": 2},
            "provider_type": {"Clinic": 4, "Doctor": 3, "Hospital": 1},
        },
        "invitations": {
            "created_cohort_current_status": {
                "PENDING": 5,
                "ACCEPTED": 4,
                "COMPLETED": 2,
                "EXPIRED": 2,
            },
            "all_current_status": {
                "PENDING": 12,
                "ACCEPTED": 31,
                "COMPLETED": 18,
                "CANCELLED": 4,
                "EXPIRED": 7,
            },
            "legacy_compatible_invitation_totals": {
                "Sent": 49,
                "Accepted or completed": 49,
                "Cancelled or expired": 11,
            },
        },
        "reviews": {
            "star_distribution": [
                {"rating": 5, "count": 7},
                {"rating": 4, "count": 3},
                {"rating": 3, "count": 1},
                {"rating": 2, "count": 0},
                {"rating": 1, "count": 0},
            ],
            "active_moderation_status": {
                "PUBLISHED": 10,
                "HIDDEN": 1,
                "PENDING": 3,
            },
            "submitted_cohort_current_status": {
                "PUBLISHED": 8,
                "HIDDEN": 2,
                "PENDING": 2,
            },
            "period_actions": {"Edited": 3, "Hidden": 2, "Published": 4},
            "top_reviewed_providers": [
                {"name": "Sample Meadow Clinic", "rating_count": 8},
                {"name": "Sample Cedar Equine", "rating_count": 6},
                {"name": "Sample Northfield Care", "rating_count": 4},
            ],
            "period_submission_leaders": [
                {"name": "Sample Meadow Clinic", "review_submissions": 4},
                {"name": "Sample Cedar Equine", "review_submissions": 3},
                {"name": "Sample Northfield Care", "review_submissions": 2},
            ],
        },
        "feedback": {
            "categories": [
                {"category": "Search & Matching", "count": 2},
                {"category": "Website / App", "count": 1},
                {"category": "Provider Experience", "count": 1},
                {"category": "Suggestion", "count": 1},
            ],
            "submitted_cohort_current_status": {
                "Pending": 2,
                "In review": 2,
                "Resolved": 1,
            },
            "current_status": {
                "Pending": 5,
                "In review": 3,
                "Resolved": 14,
                "Rejected": 2,
            },
            "ratings": {
                "distribution": [
                    {"rating": 5, "count": 3},
                    {"rating": 4, "count": 2},
                    {"rating": 3, "count": 1},
                    {"rating": 2, "count": 1},
                ],
            },
            "private_messages": "not included",
        },
        "enquiries": {
            "enquiry_type": [
                {"type": "general", "count": 4},
                {"type": "listing", "count": 3},
                {"type": "partnership", "count": 1},
                {"type": "other", "count": 1},
            ],
            "accepted_total": 9,
        },
        "subscribers": {
            "subscriber_type": [
                {"type": "HORSE_OWNER", "count": 2},
                {"type": "VET", "count": 1},
            ],
            "unique_total": 3,
        },
    }
    common["groups"] = examples[domain]
    common["definitions"] = {
        "page_categories": "Public page views grouped into broad page categories; visitor identity and browsing history are not shown.",
        "selected_cohort.roles": "Exclusive member role for accounts created in the selected period; each account is counted once.",
        "selected_cohort.verification": "Current verification state of accounts created during the selected period.",
        "submitted_cohort_current_status": "Current status of records created within the selected period.",
        "created_cohort_current_status": "Current invitation state of invitations created within the selected period.",
        "current_inventory.status": "Current provider inventory snapshot; this is not a historical population.",
        "star_distribution": "Eligible published or hidden review ratings by star value.",
        "categories": "Private feedback submissions grouped by category; message content is never included.",
    }
    return common


def dashboard_stats():
    return {
        "total_users": 384,
        "active_providers": 61,
        "provider_counts": {"hospitals": 14, "clinics": 39, "doctors": 34},
        "invitation_counts": {"sent": 49, "accepted": 38, "rejected": 11},
        "registration_counts": {
            "registrations": 246,
            "verified": 219,
            "unverified": 27,
            "horse_owners": 181,
            "stable_managers": 92,
        },
        "visitor_visits": [
            {"date": (DEMO_TODAY - timedelta(days=6 - index)).isoformat(), "count": value}
            for index, value in enumerate([78, 103, 94, 121, 116, 143, 129])
        ],
        "location_markers": [
            {
                "location_id": "sample-map-location-clinic",
                "provider_id": "sample-provider-clinic",
                "provider_name": "Sample Meadow Clinic",
                "provider_type": "CLINIC",
                "location_name": "Sample East Campus",
                "address": "Sample Road",
                "city": "Sample Northfield",
                "latitude": 0.05,
                "longitude": -30.02,
                "is_primary": True,
            },
            {
                "location_id": "sample-map-location-doctor",
                "provider_id": "sample-provider-doctor",
                "provider_name": "Sample Cedar Equine",
                "provider_type": "DOCTOR",
                "location_name": "Sample Mobile Practice",
                "address": "Sample Route",
                "city": "Sample Brook",
                "latitude": -0.06,
                "longitude": -30.09,
                "is_primary": False,
            },
            {
                "location_id": "sample-map-location-hospital",
                "provider_id": "sample-provider-hospital",
                "provider_name": "Sample Northfield Hospital",
                "provider_type": "HOSPITAL",
                "location_name": "Sample Main Campus",
                "address": "Sample Avenue",
                "city": "Sample Harbor",
                "latitude": 0.09,
                "longitude": -29.88,
                "is_primary": True,
            },
        ],
    }


def calendar_month(month):
    month = month or DEMO_TODAY.strftime("%Y-%m")
    records = [
        ("sample-visit-1", "2026-04-09", "2026-04-10", "Sample Meadow Clinic", "Sample Brook", "Sample Region"),
        ("sample-visit-2", "2026-04-14", "2026-04-14", "Sample Cedar Equine", "Sample Northfield", "Sample Region"),
        ("sample-visit-3", "2026-04-20", "2026-04-22", "Sample Prairie Veterinary", "Sample Harbor", "Sample Region"),
        ("sample-visit-4", "2026-04-27", "2026-05-02", "Sample Valley Hospital", "Sample Meadow", "Sample Region"),
    ]
    visits = [
        {
            "id": visit_id,
            "provider_id": f"sample-provider-{index}",
            "provider_name": name,
            "start_date": start,
            "end_date": end,
            "specializations": ["Equine care", "Preventive care"] if index % 2 else ["Equine care"],
            "location": {
                "name": "Sample visiting service",
                "city": city,
                "state_province": region,
                "country": "Sample Country",
            },
        }
        for index, (visit_id, start, end, name, city, region) in enumerate(records, start=1)
    ]
    return {"month": month, "today": f"{month}-14", "visits": visits}


def ranking(query):
    names = [
        "Sample Meadow Clinic",
        "Sample Cedar Equine",
        "Sample Northfield Care",
        "Sample Prairie Veterinary",
        "Sample Valley Hospital",
        "Sample Brook Mobile Care",
        "Sample Harbor Equine",
        "Sample Willow Clinic",
        "Sample Maple Veterinary",
        "Sample Ridge Animal Care",
        "Sample Lakeside Equine",
        "Sample Orchard Clinic",
        "Sample Summit Veterinary",
        "Sample Clover Hospital",
        "Sample Birch Mobile Care",
        "Sample Fern Equine Center",
        "Sample Fieldstone Clinic",
        "Sample Pine Veterinary",
        "Sample Meadowbrook Care",
        "Sample Aspen Hospital",
        "Sample Riverbend Equine",
        "Sample Hilltop Clinic",
        "Sample Sunrise Veterinary",
    ]
    rows = [
        {
            "provider_id": f"sample-provider-{index:02d}",
            "name": name,
            "provider_type": ["CLINIC", "DOCTOR", "HOSPITAL"][index % 3],
            "provider_status": "ACTIVE" if index % 6 != 5 else "INACTIVE",
            "publication_status": "PUBLISHED" if index % 5 != 4 else "UNPUBLISHED",
            "profile_views": 186 - index * 5,
            "profile_views_available": True,
            "review_submissions": 8 - index % 7,
            "average_rating": round(4.9 - (index % 6) * 0.1, 1),
            "rating_count": 17 - index % 8,
            "saved_count": 36 - index,
        }
        for index, name in enumerate(names)
    ]
    search = query.get("provider_search", [""])[0].lower()
    if search:
        rows = [row for row in rows if search in row["name"].lower()]
    sort_by = query.get("sort", ["profile_views"])[0]
    sort_direction = query.get("sort_direction", ["desc"])[0]
    rows.sort(
        key=lambda row: (row[sort_by] is None, row[sort_by] if row[sort_by] is not None else ""),
        reverse=sort_direction == "desc",
    )
    page_size = max(1, min(int(query.get("page_size", ["10"])[0]), 50))
    page = max(1, int(query.get("page", ["1"])[0]))
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    offset = (page - 1) * page_size
    return {
        "data": rows[offset:offset + page_size],
        "meta": {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages},
        "period": period_for(query),
        "timezone": TIMEZONE,
        "coverage": {"available": True, "from": "2026-01-01", "through": "2026-04-30"},
    }


def api_response(request):
    parsed = urlparse(request["url"])
    path = parsed.path
    method = request["method"].upper()
    query = parse_qs(parsed.query)

    if path == "/api/v1/auth/refresh" and method == "POST":
        return 200, {
            "access_token": "manual-only-synthetic-admin-token",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": "sample-admin-user",
                "email": "sample.admin@example.test",
                "full_name": "Sample Admin",
                "first_name": "Sample",
                "last_name": "Admin",
                "role": "admin",
                "roles": ["admin"],
                "is_active": True,
                "email_verified_at": "2026-04-01T12:00:00Z",
                "last_successful_login_at": "2026-04-30T14:00:00Z",
            },
        }
    if path in ("/api/v1/system-settings", "/api/v1/admin/system-settings") and method == "GET":
        return 200, {"timezone": TIMEZONE, "date_format": "month_day_year", "time_format": "12_hour"}
    if path == "/api/v1/admin/dashboard/stats" and method == "GET":
        return 200, dashboard_stats()
    if path == "/api/v1/admin/dashboard/visits" and method == "GET":
        return 200, calendar_month(query.get("month", [None])[0])
    if path == "/api/v1/admin/analytics/summary" and method == "GET":
        return 200, summary(query)
    if path == "/api/v1/admin/analytics/series" and method == "GET":
        return 200, series(query.get("metric", ["website_page_views"])[0], query)
    if path == "/api/v1/admin/analytics/breakdowns" and method == "GET":
        domain = query.get("domain", [""])[0]
        known_domains = {
            "traffic", "registrations", "providers", "applications", "invitations",
            "reviews", "feedback", "enquiries", "subscribers",
        }
        if domain not in known_domains:
            return 599, {"detail": {"message": f"Manual fixture failure: unsupported analytics domain {domain!r}."}}
        return 200, breakdown(domain, query)
    if path == "/api/v1/admin/analytics/provider-ranking" and method == "GET":
        return 200, ranking(query)
    if path == "/api/v1/admin/analytics/export" and method == "GET":
        dataset = query.get("dataset", ["report"])[0]
        csv = "Sample dataset,Sample value\n"
        csv += f"{dataset},Synthetic demonstration only\n"
        return 200, csv
    if path == "/api/v1/public/traffic/page-view" and method == "POST":
        # Acknowledge the app's automatic page-view write without persisting it.
        return 204, None
    return 599, {
        "detail": {
            "message": f"Manual fixture failure: no synthetic response for {method} {path}.",
            "code": "manual_fixture_missing",
        }
    }


class Browser:
    def __init__(self, websocket):
        self.websocket = websocket
        self.pending = {}
        self.sequence = 0
        self.reader = None
        self.api_requests = []
        self.fixture_failures = []
        self.browser_errors = []

    async def start(self):
        self.reader = asyncio.create_task(self.receive())

    async def command(self, method, params=None):
        self.sequence += 1
        command_id = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[command_id] = future
        await self.websocket.send(json.dumps({
            "id": command_id,
            "method": method,
            "params": params or {},
        }))
        result = await future
        if "error" in result:
            raise RuntimeError(f"CDP {method} failed: {result['error']}")
        return result.get("result", {})

    async def receive(self):
        async for raw in self.websocket:
            message = json.loads(raw)
            if "id" in message:
                future = self.pending.pop(message["id"], None)
                if future and not future.done():
                    future.set_result(message)
                continue
            event = message.get("method")
            params = message.get("params", {})
            if event == "Fetch.requestPaused":
                asyncio.create_task(self.intercept(params))
            elif event == "Runtime.exceptionThrown":
                details = params.get("exceptionDetails", {})
                self.browser_errors.append(details.get("text") or "Unhandled browser exception")
            elif event == "Log.entryAdded":
                entry = params.get("entry", {})
                if entry.get("level") == "error":
                    self.browser_errors.append(entry.get("text", "Browser console error"))
            elif event == "Network.loadingFailed" and params.get("errorText") not in {
                "net::ERR_ABORTED",
            }:
                self.browser_errors.append(
                    f"Network load failed: {params.get('errorText', 'unknown error')}"
                )

    async def fulfill(self, request_id, status, body, content_type="application/json"):
        if body is None:
            body_text = ""
        elif isinstance(body, str):
            body_text = body
        else:
            body_text = json.dumps(body)
        headers = [
            {"name": "Content-Type", "value": content_type},
            {"name": "Cache-Control", "value": "no-store"},
        ]
        await self.command("Fetch.fulfillRequest", {
            "requestId": request_id,
            "responseCode": status,
            "responseHeaders": headers,
            "body": base64.b64encode(body_text.encode("utf-8")).decode("ascii"),
        })

    async def intercept(self, params):
        request = params.get("request", {})
        parsed = urlparse(request.get("url", ""))
        if "/api/v1" not in parsed.path:
            # Fetch is scoped to /api/v1, but be defensive: never forward a
            # paused request from this handler to an unknown destination.
            await self.command("Fetch.failRequest", {
                "requestId": params["requestId"],
                "errorReason": "BlockedByClient",
            })
            return
        self.api_requests.append({
            "method": request.get("method", "GET").upper(),
            "path": parsed.path,
        })
        try:
            status, body = api_response(request)
            if status >= 599:
                self.fixture_failures.append(f"{request.get('method')} {parsed.path}")
            content_type = (
                "text/csv; charset=utf-8"
                if parsed.path == "/api/v1/admin/analytics/export"
                else "application/json; charset=utf-8"
            )
            await self.fulfill(params["requestId"], status, body, content_type)
        except Exception as exc:
            self.fixture_failures.append(
                f"{request.get('method')} {parsed.path}: {type(exc).__name__}: {exc}"
            )
            await self.fulfill(params["requestId"], 599, {
                "detail": {
                    "message": f"Manual fixture failure while fulfilling {parsed.path}: {exc}",
                    "code": "manual_fixture_error",
                }
            })

    async def evaluate(self, expression):
        result = await self.command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if "exceptionDetails" in result:
            raise RuntimeError(f"Browser evaluation failed: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    async def wait_for(self, expression, description, timeout=30):
        for _ in range(timeout * 10):
            value = await self.evaluate(expression)
            if value:
                return value
            await asyncio.sleep(0.1)
        body = await self.evaluate("document.body?.innerText || ''")
        raise AssertionError(f"Timed out waiting for {description}. Page content:\n{body[:3500]}")

    async def navigate(self, url, description):
        await self.command("Page.navigate", {"url": url})
        await self.wait_for("!!document.querySelector('body')", f"{description} document")
        await self.wait_for("document.readyState !== 'loading'", f"{description} document ready")
        await self.ensure_badge()
        await asyncio.sleep(0.15)

    async def ensure_badge(self):
        await self.evaluate("""(() => {
          const id = 'manual-sample-data-badge';
          if (document.getElementById(id)) return true;
          const badge = document.createElement('div');
          badge.id = id;
          badge.textContent = 'SAMPLE DATA — demonstration only';
          badge.setAttribute('aria-label', 'SAMPLE DATA — demonstration only');
          badge.style.cssText = [
            'position:fixed',
            'top:12px',
            'right:14px',
            'z-index:2147483647',
            'padding:8px 12px',
            'border:1px solid #fed7aa',
            'border-radius:999px',
            'background:#7c2d12',
            'color:#fff7ed',
            'box-shadow:0 2px 12px rgba(15,23,42,.22)',
            'font:700 12px/1.2 system-ui,sans-serif',
            'letter-spacing:.025em',
            'pointer-events:none',
            'white-space:nowrap'
          ].join(';');
          document.body.appendChild(badge);
          return true;
        })()""")

    async def click_text(self, selector, text, description=None, exact=True):
        comparison = (
            "e=>e.textContent.trim()==="
            if exact
            else "e=>e.textContent.trim().includes("
        )
        if exact:
            matcher = comparison + json.dumps(text) + "||e.getAttribute('aria-label')===" + json.dumps(text)
        else:
            matcher = comparison + json.dumps(text) + ")||e.getAttribute('aria-label')?.includes(" + json.dumps(text) + ")"
        expression = (
            "(() => { const nodes=[...document.querySelectorAll("
            + json.dumps(selector)
            + ")]; const node=nodes.find("
            + matcher
            + "); if(!node)return false; node.click(); return true; })()"
        )
        if not await self.evaluate(expression):
            raise AssertionError(f"Could not find {description or text!r} ({selector}).")
        await asyncio.sleep(0.2)
        await self.ensure_badge()

    async def set_value(self, selector, value, label):
        expression = (
            "(() => {const e=document.querySelector("
            + json.dumps(selector)
            + "); if(!e)return false; const p=Object.getPrototypeOf(e);"
            "const setter=Object.getOwnPropertyDescriptor(p,'value')?.set;"
            + "if(setter)setter.call(e,"
            + json.dumps(value)
            + ");else e.value="
            + json.dumps(value)
            + ";e.dispatchEvent(new Event('input',{bubbles:true}));"
            "e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()"
        )
        if not await self.evaluate(expression):
            raise AssertionError(f"Could not set {label}.")

    async def screenshot(self, asset_name):
        await self.ensure_badge()
        result = await self.command("Page.captureScreenshot", {
            "format": "png",
            "captureBeyondViewport": False,
            "fromSurface": True,
        })
        png = base64.b64decode(result["data"])
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as raw_file:
            raw_file.write(png)
            raw_path = Path(raw_file.name)
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        output = ASSET_DIR / f"{asset_name}.webp"
        converter = shutil.which("cwebp")
        if not converter:
            raise RuntimeError("cwebp is required to save compressed WebP manual screenshots.")
        try:
            subprocess.run(
                [converter, "-quiet", "-q", "82", "-m", "6", str(raw_path), "-o", str(output)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        finally:
            raw_path.unlink(missing_ok=True)
        print(f"Captured {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")

    async def set_viewport_height(self, height):
        await self.command("Emulation.setDeviceMetricsOverride", {
            "width": 1600,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": False,
        })
        await asyncio.sleep(0.15)

    async def scroll_heading_into_view(self, text, selector="h3"):
        expression = (
            "(() => {const node=[...document.querySelectorAll("
            + json.dumps(selector)
            + ")].find(e=>e.textContent.trim()==="
            + json.dumps(text)
            + "); if(!node)return false; node.scrollIntoView({block:'start'}); return true;})()"
        )
        if not await self.evaluate(expression):
            raise AssertionError(f"Could not scroll to report heading {text!r}.")
        await asyncio.sleep(0.2)

    async def scroll_summary_into_view(self, text):
        expression = (
            "(() => {const node=[...document.querySelectorAll('summary')].find(e=>e.textContent.trim()==="
            + json.dumps(text)
            + "); if(!node)return false; node.scrollIntoView({block:'start'}); return true;})()"
        )
        if not await self.evaluate(expression):
            raise AssertionError(f"Could not scroll to report disclosure {text!r}.")
        await asyncio.sleep(0.2)


async def wait_for_analytics(browser, marker, description):
    await browser.wait_for(
        "document.querySelector('[role=tabpanel]')?.innerText.includes("
        + json.dumps(marker)
        + ") && !document.querySelector('[role=tabpanel]')?.getAttribute('aria-busy')?.includes('true')",
        description,
        timeout=40,
    )
    # The report updates one animation frame after the aria-busy state clears.
    await asyncio.sleep(0.25)


async def capture_all(browser, domain):
    origin = f"https://{domain}"

    await browser.navigate(f"{origin}/admin/dashboard", "admin dashboard")
    await browser.wait_for("document.body.innerText.includes('Invitation activity')", "dashboard fixtures")
    await browser.screenshot("analytics-dashboard-overview")

    await browser.evaluate("document.querySelector('#map-heading')?.scrollIntoView({block:'start'})")
    await browser.wait_for("!!document.querySelector('[aria-label=\"Filter provider locations by type\"]')", "dashboard map controls")
    await browser.click_text("button[aria-label]", "Hide Clinic locations", "clinic map filter")
    await browser.screenshot("analytics-dashboard-map-filter")

    await browser.navigate(f"{origin}/admin/visiting-providers", "admin visits calendar")
    await browser.wait_for("document.body.innerText.includes('April 2026')", "calendar month")
    await browser.wait_for("!!document.querySelector('[aria-label=\"Calendar month navigation\"]')", "calendar controls")
    await browser.evaluate("""(() => {
      const day=[...document.querySelectorAll('[role=group] button')]
        .find(button=>button.getAttribute('aria-label')?.includes('April 14, 2026'));
      day?.click();
    })()""")
    await browser.wait_for("document.body.innerText.includes('Sample Cedar Equine')", "synthetic visit agenda")
    await browser.screenshot("analytics-dashboard-calendar")

    await browser.navigate(
        f"{origin}/admin/analytics?preset=last_30_days",
        "analytics overview",
    )
    await wait_for_analytics(browser, "New unique subscribers", "overview metrics")
    await browser.screenshot("analytics-overview-comparison")

    await browser.navigate(
        f"{origin}/admin/analytics?section=traffic&preset=last_30_days",
        "traffic analytics",
    )
    await wait_for_analytics(browser, "Page views by public page category", "traffic trend and category report")
    await browser.screenshot("analytics-traffic-trends")
    await browser.set_viewport_height(1900)
    await browser.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    await browser.screenshot("analytics-traffic-composite")
    await browser.set_viewport_height(1240)
    await browser.scroll_heading_into_view("Page views by public page category")
    await browser.screenshot("analytics-traffic-category-breakdown")

    # Switching View data table replaces the chart with its labeled values.
    await browser.navigate(
        f"{origin}/admin/analytics?section=traffic&preset=last_30_days",
        "traffic chart data-table state",
    )
    await wait_for_analytics(browser, "Page views by public page category", "traffic chart table action")
    await browser.click_text("summary", "View data table", "time-series data table")
    await browser.wait_for("document.querySelectorAll('table tbody tr').length > 0", "trend data rows")
    await browser.screenshot("analytics-traffic-data-table")

    await browser.click_text("summary", "Definitions & source coverage", "coverage disclosure")
    await browser.wait_for("document.body.innerText.includes('Traffic tracking started')", "coverage notes")
    await browser.screenshot("analytics-coverage-definitions")

    await browser.navigate(
        f"{origin}/admin/analytics?section=traffic&preset=custom&date_from=2026-04-10&date_to=2026-04-23&group_by=weekly&provider_type=CLINIC",
        "custom traffic filter state",
    )
    await wait_for_analytics(browser, "Page views by public page category", "custom traffic range")
    await browser.click_text("summary", "More filters", "advanced traffic filters")
    await browser.wait_for("document.querySelector('select')?.options.length > 1", "advanced filter options")
    await browser.screenshot("analytics-traffic-custom-filters")

    # Expand the detailed reports after loading the additional provider inventory.
    await browser.navigate(
        f"{origin}/admin/analytics?section=traffic&preset=last_30_days",
        "traffic detailed breakdowns",
    )
    await wait_for_analytics(browser, "Provider popularity", "traffic ranking panel")
    await browser.click_text("summary", "View detailed reports", "traffic detail disclosure")
    await browser.wait_for("document.body.innerText.includes('Breakdown tables')", "traffic tables")
    await browser.scroll_summary_into_view("View detailed reports")
    await browser.screenshot("analytics-traffic-breakdowns")

    # The table is a separate outcome sequence: sort, open a provider's detail,
    # advance a page, then choose and complete a safe synthetic CSV export.
    await browser.navigate(
        f"{origin}/admin/analytics?section=traffic&preset=last_30_days",
        "provider popularity ranking",
    )
    await wait_for_analytics(browser, "Provider popularity", "provider ranking")
    await browser.evaluate("document.querySelector('[aria-labelledby=\"provider-ranking-title\"]')?.scrollIntoView({block:'start'})")
    await browser.click_text("button[aria-label]", "Sort by Provider", "provider name sorting")
    await browser.wait_for("document.querySelector('[aria-labelledby=\"provider-ranking-title\"]')?.innerText.includes('Sample Willow Clinic')", "sorted provider rows")
    await browser.click_text("summary", "Provider details", "provider detail disclosure")
    await browser.wait_for("document.querySelector('[aria-labelledby=\"provider-ranking-title\"]')?.innerText.includes('Listing')", "provider detail snapshot")
    await browser.screenshot("analytics-provider-ranking-details")

    await browser.click_text("button", "Next →", "next provider ranking page")
    await browser.wait_for("new URLSearchParams(location.search).get('page') === '2'", "ranking page two")
    await browser.wait_for("document.querySelector('[aria-labelledby=\"provider-ranking-title\"]')?.innerText.includes('Sample Lakeside Equine')", "second page provider rows")
    await browser.screenshot("analytics-provider-ranking-pagination")

    await browser.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    await browser.click_text("summary", "Export CSV", "export dataset menu")
    await browser.wait_for("document.body.innerText.includes('Breakdown · Traffic')", "export choices")
    await browser.screenshot("analytics-export-dataset-selection")
    await browser.click_text("button", "Provider ranking", "provider ranking export")
    await browser.wait_for("document.body.innerText.includes('CSV downloaded.')", "synthetic CSV export outcome")
    await browser.screenshot("analytics-export-complete")

    await browser.navigate(
        f"{origin}/admin/analytics?section=registrations&preset=last_30_days",
        "member analytics",
    )
    await wait_for_analytics(browser, "Member cohort by exclusive role", "member trend and role charts")
    await browser.screenshot("analytics-members-reports")
    await browser.scroll_heading_into_view("Member cohort by exclusive role")
    await browser.screenshot("analytics-members-cohort-charts")
    await browser.click_text("summary", "View detailed reports", "member detailed reports")
    await browser.wait_for("document.body.innerText.includes('Breakdown tables')", "member detail tables")
    await browser.click_text("summary", "More filters", "member cohort filters")
    await browser.wait_for("document.body.innerText.includes('Member role')", "member filter controls")
    await browser.screenshot("analytics-members-details")
    await browser.scroll_summary_into_view("View detailed reports")
    await browser.screenshot("analytics-members-cohort-details")
    await browser.click_text("summary", "selected cohort", "member selected-cohort table", exact=False)
    await browser.wait_for("document.querySelectorAll('table tbody tr').length > 0", "member cohort table rows")
    await browser.screenshot("analytics-members-cohort-details-table")

    await browser.navigate(
        f"{origin}/admin/analytics?section=providers&preset=last_30_days&provider_type=CLINIC",
        "provider operations analytics",
    )
    await wait_for_analytics(browser, "Invitations created", "provider applications and invitation panels")
    await browser.screenshot("analytics-providers-reports")
    await browser.set_viewport_height(1900)
    await browser.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    await browser.screenshot("analytics-providers-composite")
    await browser.set_viewport_height(1240)
    await browser.scroll_heading_into_view("Applications submitted in this period · current status")
    await browser.screenshot("analytics-providers-activity-charts")
    await browser.click_text("summary", "View detailed reports", "provider detailed reports")
    await browser.wait_for("document.body.innerText.includes('Breakdown tables')", "inventory and invitation tables")
    await browser.scroll_summary_into_view("View detailed reports")
    await browser.screenshot("analytics-providers-details")

    await browser.navigate(
        f"{origin}/admin/analytics?section=reviews&preset=last_30_days",
        "reviews and feedback analytics",
    )
    await wait_for_analytics(browser, "Eligible ratings by star", "review and feedback reports")
    await browser.screenshot("analytics-reviews-reports")
    await browser.scroll_heading_into_view("Eligible ratings by star")
    await browser.screenshot("analytics-reviews-aggregate-charts")
    await browser.click_text("summary", "View detailed reports", "review and private feedback tables")
    await browser.wait_for("document.body.innerText.includes('Breakdown tables')", "review detail tables")
    await browser.scroll_summary_into_view("View detailed reports")
    await browser.screenshot("analytics-reviews-details")

    await browser.navigate(
        f"{origin}/admin/analytics?section=engagement&preset=last_30_days",
        "enquiries and subscriber analytics",
    )
    await wait_for_analytics(browser, "Accepted enquiries by type", "enquiry and subscriber reports")
    await browser.screenshot("analytics-engagement-reports")
    await browser.scroll_heading_into_view("Accepted enquiries by type")
    await browser.screenshot("analytics-engagement-type-charts")
    await browser.click_text("summary", "View detailed reports", "engagement detailed reports")
    await browser.wait_for("document.body.innerText.includes('Breakdown tables')", "enquiry and subscriber tables")
    await browser.scroll_summary_into_view("View detailed reports")
    await browser.screenshot("analytics-engagement-details")

    # Provide the filenames coordinated with the current Analytics manual
    # topics while preserving the individually useful additional captures.
    aliases = {
        "analytics-workspace-and-date-controls": "analytics-overview-comparison",
        "analytics-website-traffic": "analytics-traffic-composite",
        "analytics-member-registration-cohorts": "analytics-members-cohort-charts",
        "analytics-provider-inventory-applications-invitations": "analytics-providers-composite",
        "analytics-reviews-and-private-feedback": "analytics-reviews-aggregate-charts",
        "analytics-enquiries-and-subscribers": "analytics-engagement-type-charts",
        "analytics-trends-detail-tables-and-coverage": "analytics-coverage-definitions",
        "analytics-csv-exports": "analytics-export-dataset-selection",
    }
    for alias, source in aliases.items():
        shutil.copyfile(ASSET_DIR / f"{source}.webp", ASSET_DIR / f"{alias}.webp")
        print(f"Also saved {alias}.webp (same genuine capture as {source}.webp)")


async def main():
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "").strip()
    if not domain:
        raise RuntimeError("Set REPLIT_DEV_DOMAIN to the running frontend host.")
    if domain.startswith("https://"):
        domain = urlparse(domain).netloc
    if not shutil.which(CHROMIUM):
        raise RuntimeError(f"Chromium not found at {CHROMIUM}")

    # Refuse to attach to an unrelated browser: this capture owns its port and
    # profile and always selects the CDP target of type 'page'.
    try:
        urlopen(CDP_URL, timeout=1).read()
    except Exception:
        pass
    else:
        raise RuntimeError(f"CDP port {CDP_PORT} is already in use; refusing to reuse it.")

    profile = tempfile.mkdtemp(prefix="manual-analytics-chromium-")
    process = subprocess.Popen(
        [
            CHROMIUM,
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--disable-extensions",
            "--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        targets = None
        for _ in range(100):
            try:
                targets = json.loads(urlopen(CDP_URL, timeout=1).read())
                break
            except Exception:
                if process.poll() is not None:
                    raise RuntimeError(f"Dedicated Chromium exited with code {process.returncode}.")
                await asyncio.sleep(0.1)
        if targets is None:
            raise RuntimeError("Dedicated Chromium did not expose its CDP target.")
        target = next((item for item in targets if item.get("type") == "page"), None)
        if not target:
            raise RuntimeError("No CDP target of type 'page' was created.")
        async with websockets.connect(
            target["webSocketDebuggerUrl"],
            max_size=20_000_000,
            open_timeout=10,
        ) as websocket:
            browser = Browser(websocket)
            await browser.start()
            await browser.command("Page.enable")
            await browser.command("Runtime.enable")
            await browser.command("Log.enable")
            await browser.command("Network.enable")
            await browser.command("Network.setBypassServiceWorker", {"bypass": True})
            await browser.command("Emulation.setTimezoneOverride", {"timezoneId": TIMEZONE})
            await browser.command("Emulation.setDeviceMetricsOverride", {
                "width": 1600,
                "height": 1240,
                "deviceScaleFactor": 1,
                "mobile": False,
            })
            # All application API requests are intercepted before navigating;
            # scripts, stylesheets, and page modules remain genuine app assets.
            await browser.command("Fetch.enable", {
                "patterns": [{"urlPattern": "*api/v1*", "requestStage": "Request"}],
            })
            await capture_all(browser, domain)
            await asyncio.sleep(0.3)
            print(f"Intercepted {len(browser.api_requests)} /api/v1 requests.")
            print("API methods observed:", json.dumps({
                f"{request['method']} {request['path']}": sum(
                    1 for item in browser.api_requests if item == request
                )
                for request in browser.api_requests
            }, indent=2))
            if browser.fixture_failures:
                raise AssertionError(
                    "One or more API requests lacked an explicit fixture: "
                    + ", ".join(browser.fixture_failures)
                )
            if browser.browser_errors:
                print("Browser errors observed:", json.dumps(browser.browser_errors, indent=2))
            else:
                print("No uncaught browser exceptions, console errors, or network failures observed.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())