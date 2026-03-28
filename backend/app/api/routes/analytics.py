"""
Analytics and reporting API routes.
These endpoints provide statistics and insights for the admin dashboard.
"""

from datetime import datetime, date
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request

from ...db.supabase import db
from ...services.audit_service import audit_service, AuditAction
from ...api.deps import get_client_ip
from ...models import (
    OverviewStatsResponse,
    CategoryStatsResponse,
    CategoryStatsListResponse,
    LocationStatsResponse,
    LocationStatsListResponse,
    YearsInBusinessStatsResponse,
    YearsInBusinessListResponse,
    ActivityStatsResponse,
    ActivityStatsListResponse,
    StatusDistributionResponse,
    StatusDistributionListResponse,
    DashboardSummaryResponse,
    MonthlyTrendResponse,
    MonthlyTrendListResponse,
    WeeklyTrendResponse,
    WeeklyTrendListResponse,
    BusinessCategory,
    SupplierStatus,
)
from ...api.deps import get_current_admin
from ...core.cache import get_response_cache
from ...core.config import settings


router = APIRouter(prefix="/analytics", tags=["Analytics"])
cache = get_response_cache()


def _schedule_analytics_audit(
    current_admin: dict,
    report_type: str,
    endpoint: str,
    http_request: Optional[Request] = None,
    extra_details: Optional[dict] = None,
) -> None:
    """Fire-and-forget analytics audit so reads are not blocked by write latency."""

    async def _log() -> None:
        details = {"endpoint": endpoint}
        if extra_details:
            details.update(extra_details)

        try:
            await audit_service.log_analytics_access(
                admin_id=current_admin["id"],
                admin_email=current_admin["email"],
                action=AuditAction.ANALYTICS_ACCESSED,
                report_type=report_type,
                details=details,
                ip_address=get_client_ip(http_request) if http_request else None,
            )
        except Exception:
            # Analytics audit failures must never delay dashboard responses.
            pass

    asyncio.create_task(_log())


def _dashboard_summary_cache_key() -> str:
    return "analytics:dashboard-summary:v1"


def _analytics_cache_key(name: str, **params: Optional[object]) -> str:
    parts = [f"{k}={params[k]}" for k in sorted(params.keys())]
    return f"analytics:{name}:v1" + (":" + "|".join(parts) if parts else "")


@router.get(
    "/cache-stats",
    summary="Get analytics cache stats",
    description="Return lightweight cache hit/miss and invalidation counters for diagnostics."
)
async def get_analytics_cache_stats(current_admin: dict = Depends(get_current_admin)):
    """Expose analytics cache diagnostics for admins."""
    return await cache.get_stats()


@router.get(
    "/overview",
    response_model=OverviewStatsResponse,
    summary="Get overview statistics",
    description="Get high-level overview statistics for the dashboard."
)
async def get_overview_stats(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get overview statistics."""
    _schedule_analytics_audit(current_admin, "overview_stats", "/analytics/overview", http_request)

    cache_key = _analytics_cache_key("overview")
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    stats = await db.get_overview_stats()
    payload = OverviewStatsResponse(**stats).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/categories",
    response_model=CategoryStatsListResponse,
    summary="Get category statistics",
    description="Get supplier count and breakdown by business category."
)
async def get_category_stats(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get statistics grouped by business category."""
    _schedule_analytics_audit(current_admin, "category_stats", "/analytics/categories", http_request)

    cache_key = _analytics_cache_key("categories")
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    data = await db.get_supplier_count_by_category()
    
    # Calculate total for percentage
    total = sum(item["total_count"] for item in data)
    
    items = []
    for item in data:
        try:
            category = BusinessCategory(item["category"])
        except ValueError:
            # Legacy category value still in DB but removed from the enum — skip gracefully
            continue
        items.append(CategoryStatsResponse(
            category=category,
            category_display=category.value.replace("_", " ").title(),
            total_count=item["total_count"],
            approved_count=item["approved_count"],
            pending_count=item["pending_count"],
            rejected_count=item["rejected_count"],
            percentage=round((item["total_count"] / total * 100), 2) if total > 0 else 0.0,
        ))
    
    payload = CategoryStatsListResponse(
        items=items,
        total_suppliers=total
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/locations",
    response_model=LocationStatsListResponse,
    summary="Get location statistics",
    description="Get supplier count and breakdown by location (city or country)."
)
async def get_location_stats(
    level: str = Query(default="city", regex="^(city|country)$", description="Location level: city or country"),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get statistics grouped by location (city or country)."""
    _schedule_analytics_audit(
        current_admin,
        f"location_stats_{level}",
        "/analytics/locations",
        http_request,
        {"level": level},
    )

    cache_key = _analytics_cache_key("locations", level=level)
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload
    
    # Choose the appropriate function based on level
    if level == "country":
        data = await db.get_location_stats_by_country()
    else:
        data = await db.get_location_stats()
    
    # Both functions now return: location, count, approved_count, pending_count, percentage
    items = []
    total_suppliers = 0
    for item in data:
        items.append(LocationStatsResponse(
            location=item["location"],
            total_count=item["count"],
            approved_count=item["approved_count"],
            pending_count=item["pending_count"],
            percentage=float(item["percentage"]) if item["percentage"] else 0.0,
        ))
        total_suppliers += item["count"]
    
    payload = LocationStatsListResponse(
        items=items,
        total_suppliers=total_suppliers
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/years-in-business",
    response_model=YearsInBusinessListResponse,
    summary="Get years in business distribution",
    description="Get distribution of suppliers by years in business."
)
async def get_years_in_business_stats(current_admin: dict = Depends(get_current_admin)):
    """Get statistics grouped by years in business ranges."""
    # Get all suppliers
    cache_key = _analytics_cache_key("years-in-business")
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    suppliers_result = await db.list_suppliers(
        page=1,
        page_size=10000  # Get all for analysis
    )
    suppliers = suppliers_result["items"]
    
    # Define ranges
    ranges = [
        {"label": "0-2 years", "min": 0, "max": 2},
        {"label": "3-5 years", "min": 3, "max": 5},
        {"label": "6-10 years", "min": 6, "max": 10},
        {"label": "11-20 years", "min": 11, "max": 20},
        {"label": "20+ years", "min": 21, "max": None},
    ]
    
    total = len(suppliers)
    average_years = sum(s["years_in_business"] for s in suppliers) / total if total > 0 else 0
    
    items = []
    for range_def in ranges:
        if range_def["max"] is None:
            count = len([s for s in suppliers if s["years_in_business"] >= range_def["min"]])
        else:
            count = len([
                s for s in suppliers
                if range_def["min"] <= s["years_in_business"] <= range_def["max"]
            ])
        
        items.append(YearsInBusinessStatsResponse(
            range_label=range_def["label"],
            min_years=range_def["min"],
            max_years=range_def["max"],
            count=count,
            percentage=round((count / total * 100), 2) if total > 0 else 0.0,
        ))
    
    payload = YearsInBusinessListResponse(
        items=items,
        total_suppliers=total,
        average_years=round(average_years, 1)
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/status-distribution",
    response_model=StatusDistributionListResponse,
    summary="Get status distribution",
    description="Get count of suppliers by application status."
)
async def get_status_distribution(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get distribution of suppliers by status."""
    _schedule_analytics_audit(current_admin, "status_distribution", "/analytics/status-distribution", http_request)

    cache_key = _analytics_cache_key("status-distribution")
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    data = await db.get_status_distribution()
    
    total = sum(item["count"] for item in data)
    
    items = []
    for item in data:
        status_enum = SupplierStatus(item["status"])
        items.append(StatusDistributionResponse(
            status=status_enum,
            status_display=status_enum.value.replace("_", " ").title(),
            count=item["count"],
            percentage=round((item["count"] / total * 100), 2) if total > 0 else 0.0,
        ))
    
    payload = StatusDistributionListResponse(
        items=items,
        total=total
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/monthly-trends",
    response_model=MonthlyTrendListResponse,
    summary="Get monthly trends",
    description="Get monthly registration, approval, and rejection trends."
)
async def get_monthly_trends(
    year: int = Query(default=datetime.now().year, ge=2020, le=2100),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get monthly trends for a specific year."""
    _schedule_analytics_audit(
        current_admin,
        "monthly_trends",
        "/analytics/monthly-trends",
        http_request,
        {"year": year},
    )

    cache_key = _analytics_cache_key("monthly-trends", year=year)
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload
    
    # get_monthly_trends uses months_back parameter, not year
    # Calculate months back from current date to the start of the requested year
    current_date = datetime.now()
    months_back = (current_date.year - year) * 12 + current_date.month
    months_back = max(12, months_back)  # At least 12 months
    
    data = await db.get_monthly_trends(months_back)
    
    # Filter to only include the requested year
    items = []
    for item in data:
        if item["year"] == year:
            items.append(MonthlyTrendResponse(
                month=item["month"].strip(),
                year=item["year"],
                registrations=item["submitted"],
                approvals=item["approved"],
                rejections=item["rejected"],
            ))
    
    payload = MonthlyTrendListResponse(
        items=items,
        period_months=len(items)
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/weekly-trends",
    response_model=WeeklyTrendListResponse,
    summary="Get weekly trends",
    description="Get weekly registration, approval, and rejection trends."
)
async def get_weekly_trends(
    weeks: int = Query(default=12, ge=1, le=52, description="Number of weeks to look back"),
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get weekly trends for the specified number of weeks."""
    _schedule_analytics_audit(
        current_admin,
        "weekly_trends",
        "/analytics/weekly-trends",
        http_request,
        {"weeks": weeks},
    )

    cache_key = _analytics_cache_key("weekly-trends", weeks=weeks)
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload
    
    data = await db.get_weekly_trends(weeks)
    
    items = []
    for item in data:
        items.append(WeeklyTrendResponse(
            week_label=item["week_label"].strip(),
            year=item["year"],
            week_number=item["week_number"],
            week_start=item["week_start"],
            registrations=item["submitted"],
            approvals=item["approved"],
            rejections=item["rejected"],
        ))
    
    payload = WeeklyTrendListResponse(
        items=items,
        period_weeks=len(items)
    ).model_dump(mode="json")
    await cache.set_json(
        cache_key,
        payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
    summary="Get complete dashboard summary",
    description="Get all key metrics for the admin dashboard in one call."
)
async def get_dashboard_summary(
    http_request: Request = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get comprehensive dashboard summary with all key metrics."""
    _schedule_analytics_audit(current_admin, "dashboard_summary", "/analytics/dashboard-summary", http_request)
    
    cache_key = _dashboard_summary_cache_key()
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        return cached_payload

    # Get high-volume dashboard sections in one await to reduce response time.
    overview_task = db.get_overview_stats()
    category_task = db.get_supplier_count_by_category()
    location_task = db.get_location_stats()
    status_task = db.get_status_distribution()
    submitted_apps_task = db.list_suppliers(
        status=SupplierStatus.SUBMITTED.value,
        category=None,
        page=1,
        page_size=5,
        order_by="submitted_at",
        ascending=False,
    )
    incomplete_apps_task = db.list_suppliers(
        status=SupplierStatus.INCOMPLETE.value,
        category=None,
        page=1,
        page_size=5,
        order_by="created_at",
        ascending=False,
    )

    (
        overview_data,
        category_data,
        location_data,
        status_data,
        submitted_apps_result,
        incomplete_apps_result,
    ) = await asyncio.gather(
        overview_task,
        category_task,
        location_task,
        status_task,
        submitted_apps_task,
        incomplete_apps_task,
    )

    overview = OverviewStatsResponse(**overview_data)

    # Get category distribution
    total_suppliers = sum(item["total_count"] for item in category_data)
    category_distribution = []
    for item in category_data[:10]:  # Expand window to get 5 valid after skipping legacy
        try:
            cat_enum = BusinessCategory(item["category"])
        except ValueError:
            continue  # Legacy value still in DB — skip without crashing
        category_distribution.append(
            CategoryStatsResponse(
                category=cat_enum,
                category_display=item["category"].replace("_", " ").title(),
                total_count=item["total_count"],
                approved_count=item["approved_count"],
                pending_count=item["pending_count"],
                rejected_count=item["rejected_count"],
                percentage=round((item["total_count"] / total_suppliers * 100), 2) if total_suppliers > 0 else 0.0,
            )
        )
        if len(category_distribution) == 5:
            break  # We have our top 5 valid categories
    
    # Get location distribution
    location_distribution = [
        LocationStatsResponse(
            location=item["location"],
            total_count=item["count"],
            approved_count=0,  # Not provided by get_location_stats
            pending_count=0,  # Not provided by get_location_stats
            percentage=float(item["percentage"]) if item["percentage"] else 0.0,
        )
        for item in location_data[:5]  # Top 5 locations
    ]
    
    # Get status distribution
    total = sum(item["count"] for item in status_data)
    status_distribution = [
        StatusDistributionResponse(
            status=SupplierStatus(item["status"]),
            status_display=item["status"].replace("_", " ").title(),
            count=item["count"],
            percentage=round((item["count"] / total * 100), 2) if total > 0 else 0.0,
        )
        for item in status_data
    ]
    
    # Count pending reviews — only SUBMITTED (no admin has opened the application yet)
    pending_reviews = sum(
        item["count"] for item in status_data
        if item["status"] == "SUBMITTED"
    )
    
    merged_recent_apps = [
        *(submitted_apps_result.get("items", []) or []),
        *(incomplete_apps_result.get("items", []) or []),
    ]

    def _activity_ts(app: dict) -> datetime:
        raw = app.get("submitted_at") or app.get("created_at")
        if not raw:
            return datetime.min
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return datetime.min

    merged_recent_apps.sort(key=_activity_ts, reverse=True)

    # Format recent applications for frontend
    recent_applications = [
        {
            "id": app["id"],
            "companyName": app["company_name"],
            "email": app["email"],
            "status": app["status"],
            "createdAt": app["created_at"],
            "submittedAt": app.get("submitted_at"),
        }
        for app in merged_recent_apps[:10]
    ]
    
    response_payload = DashboardSummaryResponse(
        overview=overview,
        category_distribution=category_distribution,
        location_distribution=location_distribution,
        status_distribution=status_distribution,
        recent_applications=recent_applications,
        recent_registrations=overview_data["applications_this_month"],
        pending_reviews=pending_reviews,
        last_updated=datetime.utcnow(),
    ).model_dump(mode="json")

    await cache.set_json(
        cache_key,
        response_payload,
        ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS,
    )

    return response_payload
