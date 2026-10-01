"""Protected administrator analytics reporting and sanitized CSV exports."""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.db.session import get_db
from app.repositories.admin_analytics_repository import AdminAnalyticsRepository
from app.schemas.admin_analytics import (
    AnalyticsDataset,
    AnalyticsDomain,
    AnalyticsFilters,
    AnalyticsSort,
)
from app.services.admin_analytics_service import (
    AdminAnalyticsService,
    AnalyticsMetricNotFound,
)

router = APIRouter(
    prefix="/admin/analytics",
    tags=["Admin Analytics"],
    dependencies=[Depends(require_role("admin"))],
)
_DB = Annotated[Session, Depends(get_db)]
MAX_EXPORT_ROWS = 5_000


def _service(db: _DB) -> AdminAnalyticsService:
    return AdminAnalyticsService(AdminAnalyticsRepository(db))


_Service = Annotated[AdminAnalyticsService, Depends(_service)]


def _invalid_metric(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "unsupported_analytics_selection",
            "message": str(error),
        },
    )


@router.get("/summary")
def analytics_summary(
    svc: _Service,
    filters: Annotated[AnalyticsFilters, Depends()],
) -> dict[str, Any]:
    """Return period additions and separately labelled current snapshots."""
    try:
        return svc.summary(filters)
    except ValueError as error:
        raise _invalid_metric(error) from None


@router.get("/series")
def analytics_series(
    svc: _Service,
    filters: Annotated[AnalyticsFilters, Depends()],
    metric: str = Query(..., min_length=1, max_length=64),
) -> dict[str, Any]:
    try:
        return svc.series(metric, filters)
    except (AnalyticsMetricNotFound, ValueError) as error:
        raise _invalid_metric(error) from None


@router.get("/breakdowns")
def analytics_breakdowns(
    svc: _Service,
    filters: Annotated[AnalyticsFilters, Depends()],
    domain: AnalyticsDomain = Query(...),
) -> dict[str, Any]:
    try:
        return svc.breakdowns(domain, filters)
    except ValueError as error:
        raise _invalid_metric(error) from None


@router.get("/provider-ranking")
def provider_ranking(
    svc: _Service,
    filters: Annotated[AnalyticsFilters, Depends()],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: AnalyticsSort = Query(AnalyticsSort.PROFILE_VIEWS),
    sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    try:
        return svc.provider_ranking(
            filters,
            page=page,
            page_size=page_size,
            sort=sort.value,
            direction=sort_direction,
        )
    except ValueError as error:
        raise _invalid_metric(error) from None


def _csv_cell(value: Any) -> str:
    """Escape spreadsheet formulas in all user-visible string fields."""
    if value is None:
        return ""
    text_value = str(value)
    if text_value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text_value
    return text_value


def _csv_line(values: list[Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([_csv_cell(value) for value in values])
    return buffer.getvalue()


def _flatten_breakdown(value: Any, prefix: str = "") -> list[list[Any]]:
    rows: list[list[Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_breakdown(item, label))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_flatten_breakdown(item, f"{prefix}.{index}"))
    else:
        rows.append([prefix, value])
    return rows


@router.get("/export")
def export_analytics(
    svc: _Service,
    filters: Annotated[AnalyticsFilters, Depends()],
    dataset: AnalyticsDataset = Query(...),
    metric: str | None = Query(None, max_length=64),
    domain: AnalyticsDomain | None = Query(None),
    sort: AnalyticsSort = Query(AnalyticsSort.PROFILE_VIEWS),
    sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
) -> StreamingResponse:
    """Stream a bounded, PII-minimized CSV using the visible report definitions."""
    is_truncated = False
    export_metadata: dict[str, Any] = {}
    try:
        if dataset == AnalyticsDataset.SERIES:
            if metric is None:
                raise AnalyticsMetricNotFound("series exports require metric.")
            payload = svc.series(metric, filters)
            if payload["data"] is None:
                raise AnalyticsMetricNotFound("The requested series is outside its coverage window.")
            header = ["bucket", "value"]
            rows = [[point["bucket"], point["value"]] for point in payload["data"]]
            export_metadata = {
                "timezone": payload["timezone"],
                "date_from": payload["period"]["date_from"],
                "date_to": payload["period"]["date_to"],
                "group_by": payload["period"]["group_by"],
                "filters": filters.model_dump(mode="json", exclude_none=True),
                "definitions": payload["definition"],
                "coverage": payload["coverage"],
            }
            if len(rows) > MAX_EXPORT_ROWS:
                rows = rows[:MAX_EXPORT_ROWS]
                is_truncated = True
        elif dataset == AnalyticsDataset.BREAKDOWNS:
            if domain is None:
                raise AnalyticsMetricNotFound("breakdown exports require domain.")
            payload = svc.breakdowns(domain, filters)
            header = ["section", "metric", "value"]
            export_metadata = {
                "timezone": payload["timezone"],
                "date_from": payload["period"]["date_from"],
                "date_to": payload["period"]["date_to"],
                "group_by": payload["period"]["group_by"],
                "filters": filters.model_dump(mode="json", exclude_none=True),
                "definitions": payload["definitions"],
                "coverage": payload["coverage"],
            }
            rows = []
            for group_name, group_values in payload["groups"].items():
                rows.extend(
                    [[group_name, *row] for row in _flatten_breakdown(group_values)]
                )
            is_truncated = len(rows) > MAX_EXPORT_ROWS
            rows = rows[:MAX_EXPORT_ROWS]
        else:
            rows = []
            page = 1
            total = 0
            first_payload = None
            while len(rows) < MAX_EXPORT_ROWS:
                page_payload = svc.provider_ranking(
                    filters,
                    page=page,
                    page_size=100,
                    sort=sort.value,
                    direction=sort_direction,
                )
                if first_payload is None:
                    first_payload = page_payload
                total = page_payload["meta"]["total"]
                rows.extend(page_payload["data"])
                if page_payload["meta"]["total_pages"] <= page:
                    break
                page += 1
            rows = rows[:MAX_EXPORT_ROWS]
            is_truncated = total > len(rows)
            assert first_payload is not None
            export_metadata = {
                "timezone": first_payload["timezone"],
                "date_from": first_payload["period"]["date_from"],
                "date_to": first_payload["period"]["date_to"],
                "group_by": first_payload["period"]["group_by"],
                "filters": filters.model_dump(mode="json", exclude_none=True),
                "sort": sort.value,
                "sort_direction": sort_direction,
                "definitions": {
                    "profile_views": "Successful member-accessible provider-profile views during the period.",
                    "review_submissions": "Initial review records created during the period; edits are not counted.",
                    "average_rating": "Current average across undeleted PUBLISHED or HIDDEN provider ratings.",
                    "rating_count": "Current count of undeleted PUBLISHED or HIDDEN provider ratings.",
                    "saved_count": "Current number of unique members saving the provider.",
                },
                "coverage": first_payload["profile_views_coverage"],
            }
            header = [
                "provider_id",
                "provider_name",
                "provider_type",
                "provider_status",
                "publication_status",
                "profile_views",
                "review_submissions",
                "average_rating",
                "rating_count",
                "saved_count",
            ]
            rows = [
                [
                    row["provider_id"],
                    row["name"],
                    row["provider_type"],
                    row["provider_status"],
                    row["publication_status"],
                    row["profile_views"],
                    row["review_submissions"],
                    row["average_rating"],
                    row["rating_count"],
                    row["saved_count"],
                ]
                for row in rows
            ]
    except (AnalyticsMetricNotFound, ValueError) as error:
        raise _invalid_metric(error) from None

    if dataset == AnalyticsDataset.SERIES and not rows:
        header = ["bucket", "value"]
    if dataset == AnalyticsDataset.BREAKDOWNS and not rows:
        header = ["section", "metric", "value"]

    def stream():
        width = len(header)
        for key, value in export_metadata.items():
            metadata_row = [
                f"# {key}",
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list))
                else value,
            ]
            yield _csv_line(metadata_row + [""] * max(0, width - len(metadata_row)))
        yield _csv_line(header)
        for row in rows:
            yield _csv_line(row)
        if is_truncated:
            notice = ["notice", f"Export limited to {MAX_EXPORT_ROWS} rows"]
            yield _csv_line(notice + [""] * max(0, width - len(notice)))

    filename = f"analytics-{dataset.value}-{date.today().isoformat()}.csv"
    return StreamingResponse(
        stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )